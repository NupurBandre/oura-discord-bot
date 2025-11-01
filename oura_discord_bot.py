#!/usr/bin/env python3
"""
Oura Ring 4 Discord Price Tracker Bot
A Discord bot that monitors prices and sends notifications to your server
"""

import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import asyncio
import re
from typing import Optional, Dict, List

class OuraPriceTracker:
    def __init__(self):
        self.price_history = []
        self.retailers = {
            'amazon': {
                'name': 'Amazon',
                'base_url': 'https://www.amazon.com/dp/B0DJCX5KQG',
                'colors': ['silver', 'black', 'gold']
            },
            'target': {
                'name': 'Target',
                'base_url': 'https://www.target.com/p/oura-ring-4/-/A-93747936',
                'colors': ['black']
            },
            'oura': {
                'name': 'Oura Official',
                'base_urls': {
                    'silver': 'https://ouraring.com/store/rings/oura-ring-4/silver',
                    'black': 'https://ouraring.com/store/rings/oura-ring-4/stealth',
                    'gold': 'https://ouraring.com/store/rings/oura-ring-4/gold',
                    'rose_gold': 'https://ouraring.com/store/rings/oura-ring-4/rose-gold'
                },
                'colors': ['silver', 'black', 'gold', 'rose_gold']
            }
        }
    
    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    
    def extract_price(self, url: str, retailer: str) -> Optional[float]:
        """Extract price from retailer website"""
        try:
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text()
            
            # Look for price patterns
            patterns = [
                r'\$(\d{3}(?:\.\d{2})?)',  # $349 or $349.99
                r'(\d{3}(?:\.\d{2})?)\s*USD',  # 349 USD
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    price = float(match.group(1))
                    if 200 <= price <= 600:  # Reasonable range for Oura Ring
                        return price
            
            return None
        except Exception as e:
            print(f"Error fetching price from {retailer}: {e}")
            return None
    
    async def check_all_prices(self, tracked_colors: List[str]) -> List[Dict]:
        """Check prices across all retailers"""
        results = []
        
        for retailer_key, retailer_data in self.retailers.items():
            for color in tracked_colors:
                if color not in retailer_data['colors']:
                    continue
                
                # Determine URL
                if retailer_key == 'oura' and 'base_urls' in retailer_data:
                    url = retailer_data['base_urls'].get(color)
                else:
                    url = retailer_data['base_url']
                
                if not url:
                    continue
                
                # Fetch price
                price = self.extract_price(url, retailer_data['name'])
                
                if price:
                    result = {
                        'timestamp': datetime.now().isoformat(),
                        'retailer': retailer_data['name'],
                        'color': color,
                        'price': price,
                        'url': url
                    }
                    results.append(result)
                
                # Be respectful with requests
                await asyncio.sleep(2)
        
        return results


class OuraBotConfig:
    """Bot configuration management"""
    def __init__(self, config_file='bot_config.json'):
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                'target_price': 299.0,
                'check_interval': 60,  # Check every 60 minutes
                'tracked_colors': ['silver', 'black', 'gold'],
                'tracking_enabled': False,
                'alert_channel_id': None
            }
            self.save_config()
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value
        self.save_config()


# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize tracker and config
tracker = OuraPriceTracker()
config = OuraBotConfig()


@bot.event
async def on_ready():
    print(f'✅ {bot.user} is now online!')
    print(f'📊 Bot is in {len(bot.guilds)} server(s)')
    print(f'🔍 Use !help to see available commands')
    
    # Start price checking if enabled
    if config.get('tracking_enabled'):
        if not price_check_loop.is_running():
            price_check_loop.start()


@bot.command(name='start', help='Start price tracking')
async def start_tracking(ctx):
    """Start the price tracking loop"""
    if config.get('tracking_enabled'):
        await ctx.send('⚠️ Price tracking is already running!')
        return
    
    config.set('tracking_enabled', True)
    config.set('alert_channel_id', ctx.channel.id)
    
    if not price_check_loop.is_running():
        price_check_loop.start()
    
    embed = discord.Embed(
        title='✅ Price Tracking Started!',
        description=f'Monitoring Oura Ring 4 prices every {config.get("check_interval")} minutes',
        color=discord.Color.green()
    )
    embed.add_field(name='Target Price', value=f'${config.get("target_price"):.2f}', inline=True)
    embed.add_field(name='Tracking', value=', '.join(config.get('tracked_colors')), inline=True)
    embed.add_field(name='Alert Channel', value=ctx.channel.mention, inline=False)
    
    await ctx.send(embed=embed)


@bot.command(name='stop', help='Stop price tracking')
async def stop_tracking(ctx):
    """Stop the price tracking loop"""
    if not config.get('tracking_enabled'):
        await ctx.send('⚠️ Price tracking is not running!')
        return
    
    config.set('tracking_enabled', False)
    
    embed = discord.Embed(
        title='🛑 Price Tracking Stopped',
        description='Price monitoring has been paused',
        color=discord.Color.red()
    )
    
    await ctx.send(embed=embed)


@bot.command(name='setprice', help='Set target alert price (e.g., !setprice 299)')
async def set_price(ctx, price: float):
    """Set the target price for alerts"""
    if price < 100 or price > 600:
        await ctx.send('❌ Please enter a valid price between $100 and $600')
        return
    
    config.set('target_price', price)
    
    embed = discord.Embed(
        title='💰 Target Price Updated',
        description=f'You will be alerted when prices drop to ${price:.2f} or below',
        color=discord.Color.blue()
    )
    
    await ctx.send(embed=embed)


@bot.command(name='check', help='Check current prices immediately')
async def check_now(ctx):
    """Manually trigger a price check"""
    await ctx.send('🔍 Checking prices across all retailers... This may take a minute.')
    
    results = await tracker.check_all_prices(config.get('tracked_colors'))
    
    if not results:
        await ctx.send('❌ Could not fetch any prices. Retailers may be blocking requests.')
        return
    
    # Create embed with results
    embed = discord.Embed(
        title='📊 Current Oura Ring 4 Prices',
        description=f'Checked at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        color=discord.Color.blue()
    )
    
    # Group by retailer
    by_retailer = {}
    for result in results:
        retailer = result['retailer']
        if retailer not in by_retailer:
            by_retailer[retailer] = []
        by_retailer[retailer].append(result)
    
    for retailer, prices in by_retailer.items():
        price_text = '\n'.join([
            f"**{p['color'].title()}**: ${p['price']:.2f}"
            for p in prices
        ])
        embed.add_field(name=f'🏪 {retailer}', value=price_text, inline=False)
    
    # Find lowest price
    lowest = min(results, key=lambda x: x['price'])
    embed.add_field(
        name='🏆 Best Price',
        value=f"${lowest['price']:.2f} - {lowest['retailer']} ({lowest['color'].title()})",
        inline=False
    )
    
    await ctx.send(embed=embed)


@bot.command(name='colors', help='Set which colors to track (e.g., !colors silver black gold)')
async def set_colors(ctx, *colors):
    """Set which ring colors to track"""
    valid_colors = ['silver', 'black', 'gold', 'rose_gold', 'stealth']
    colors = [c.lower() for c in colors]
    
    invalid = [c for c in colors if c not in valid_colors]
    if invalid:
        await ctx.send(f'❌ Invalid colors: {", ".join(invalid)}\nValid options: {", ".join(valid_colors)}')
        return
    
    if not colors:
        await ctx.send(f'❌ Please specify at least one color\nValid options: {", ".join(valid_colors)}')
        return
    
    config.set('tracked_colors', colors)
    
    embed = discord.Embed(
        title='🎨 Tracking Colors Updated',
        description=f'Now tracking: {", ".join([c.title() for c in colors])}',
        color=discord.Color.purple()
    )
    
    await ctx.send(embed=embed)


@bot.command(name='interval', help='Set check interval in minutes (e.g., !interval 30)')
async def set_interval(ctx, minutes: int):
    """Set how often to check prices"""
    if minutes < 10 or minutes > 1440:
        await ctx.send('❌ Please enter a value between 10 minutes and 1440 minutes (24 hours)')
        return
    
    config.set('check_interval', minutes)
    
    # Restart loop with new interval
    if config.get('tracking_enabled'):
        price_check_loop.restart()
    
    embed = discord.Embed(
        title='⏱️ Check Interval Updated',
        description=f'Prices will be checked every {minutes} minutes',
        color=discord.Color.orange()
    )
    
    await ctx.send(embed=embed)


@bot.command(name='status', help='Show bot status and configuration')
async def show_status(ctx):
    """Display current bot status and settings"""
    embed = discord.Embed(
        title='🤖 Oura Ring Price Tracker Status',
        color=discord.Color.blue()
    )
    
    # Status
    status = '🟢 Running' if config.get('tracking_enabled') else '🔴 Stopped'
    embed.add_field(name='Status', value=status, inline=True)
    
    # Target price
    embed.add_field(
        name='Target Price',
        value=f"${config.get('target_price'):.2f}",
        inline=True
    )
    
    # Check interval
    embed.add_field(
        name='Check Interval',
        value=f"{config.get('check_interval')} minutes",
        inline=True
    )
    
    # Tracked colors
    embed.add_field(
        name='Tracked Colors',
        value=', '.join([c.title() for c in config.get('tracked_colors')]),
        inline=False
    )
    
    # Alert channel
    channel_id = config.get('alert_channel_id')
    if channel_id:
        channel = bot.get_channel(channel_id)
        embed.add_field(
            name='Alert Channel',
            value=channel.mention if channel else 'Unknown',
            inline=False
        )
    
    await ctx.send(embed=embed)


@bot.command(name='history', help='Show recent price history')
async def show_history(ctx):
    """Display recent price checks"""
    if not tracker.price_history:
        await ctx.send('📊 No price history available yet. Use `!check` to start tracking.')
        return
    
    # Get last 10 entries
    recent = tracker.price_history[-10:]
    
    embed = discord.Embed(
        title='📈 Recent Price History',
        color=discord.Color.gold()
    )
    
    for entry in recent:
        timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%m/%d %H:%M')
        embed.add_field(
            name=f"{entry['retailer']} - {entry['color'].title()}",
            value=f"${entry['price']:.2f} at {timestamp}",
            inline=True
        )
    
    await ctx.send(embed=embed)


@tasks.loop(minutes=60)
async def price_check_loop():
    """Background task that checks prices periodically"""
    if not config.get('tracking_enabled'):
        return
    
    print(f'🔍 Running scheduled price check at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    
    results = await tracker.check_all_prices(config.get('tracked_colors'))
    
    if not results:
        print('❌ No prices fetched in this check')
        return
    
    # Save to history
    tracker.price_history.extend(results)
    
    # Check for prices below target
    target_price = config.get('target_price')
    deals = [r for r in results if r['price'] <= target_price]
    
    if deals:
        # Send alert
        channel_id = config.get('alert_channel_id')
        if channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                for deal in deals:
                    embed = discord.Embed(
                        title='🚨 PRICE ALERT! 🚨',
                        description=f"Oura Ring 4 price dropped to ${deal['price']:.2f}!",
                        color=discord.Color.red()
                    )
                    embed.add_field(name='Retailer', value=deal['retailer'], inline=True)
                    embed.add_field(name='Color', value=deal['color'].title(), inline=True)
                    embed.add_field(name='Price', value=f"${deal['price']:.2f}", inline=True)
                    embed.add_field(name='Your Target', value=f"${target_price:.2f}", inline=True)
                    embed.add_field(name='Link', value=f"[Buy Now]({deal['url']})", inline=False)
                    embed.set_footer(text=f"Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    await channel.send(embed=embed)
                    await channel.send(f"@everyone 🔔 Great deal on Oura Ring 4!")


@price_check_loop.before_loop
async def before_price_check():
    """Wait until bot is ready before starting loop"""
    await bot.wait_until_ready()
    # Update loop interval from config
    price_check_loop.change_interval(minutes=config.get('check_interval'))


@bot.command(name='help_oura', help='Show detailed help for all commands')
async def show_help(ctx):
    """Show comprehensive help message"""
    embed = discord.Embed(
        title='🤖 Oura Ring 4 Price Tracker - Help',
        description='Monitor Oura Ring 4 prices and get alerts when deals appear!',
        color=discord.Color.blue()
    )
    
    commands_help = {
        '!start': 'Start automatic price tracking',
        '!stop': 'Stop automatic price tracking',
        '!check': 'Check current prices immediately',
        '!setprice <amount>': 'Set target alert price (e.g., !setprice 299)',
        '!colors <color1> <color2>': 'Set colors to track (e.g., !colors silver black)',
        '!interval <minutes>': 'Set check frequency (e.g., !interval 30)',
        '!status': 'Show bot status and configuration',
        '!history': 'Show recent price history',
        '!help_oura': 'Show this help message'
    }
    
    for cmd, desc in commands_help.items():
        embed.add_field(name=cmd, value=desc, inline=False)
    
    embed.add_field(
        name='📋 Example Workflow',
        value='1️⃣ `!setprice 299` - Set your target price\n'
              '2️⃣ `!colors silver black` - Choose colors to track\n'
              '3️⃣ `!interval 30` - Check every 30 minutes\n'
              '4️⃣ `!start` - Start tracking!\n'
              '5️⃣ Wait for alerts when prices drop! 🎉',
        inline=False
    )
    
    await ctx.send(embed=embed)


def main():
    """Main function to run the bot"""
    import sys
    
    # Check for bot token
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not token:
        print('❌ ERROR: DISCORD_BOT_TOKEN environment variable not set!')
        print('\nPlease set your bot token:')
        print('  Linux/Mac: export DISCORD_BOT_TOKEN="your_token_here"')
        print('  Windows: set DISCORD_BOT_TOKEN=your_token_here')
        print('\nOr create a .env file with: DISCORD_BOT_TOKEN=your_token_here')
        sys.exit(1)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print('❌ ERROR: Invalid bot token!')
        print('Please check your DISCORD_BOT_TOKEN environment variable')
        sys.exit(1)
    except Exception as e:
        print(f'❌ ERROR: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
