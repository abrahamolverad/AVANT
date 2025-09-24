"""
Outreach Manager for automated account discovery and messaging
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
from instagram_client import InstagramClient
from ai_response_system import AIResponseSystem
from database import DatabaseManager, TargetAccount, OutreachCampaign
from config import settings

logger = logging.getLogger(__name__)

class OutreachManager:
    def __init__(self, db_manager: DatabaseManager):
        self.instagram_client = InstagramClient()
        self.ai_system = AIResponseSystem()
        self.db_manager = db_manager
        self.is_running = False
    
    async def start_outreach_campaign(self, campaign_name: str, target_industry: str, 
                                    target_location: str, message_template: str = None) -> bool:
        """Start a new outreach campaign"""
        try:
            # Create campaign in database
            campaign = self.db_manager.create_outreach_campaign(
                name=campaign_name,
                target_industry=target_industry,
                target_location=target_location,
                message_template=message_template or self._get_default_template(target_industry)
            )
            
            logger.info(f"Started outreach campaign: {campaign_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting outreach campaign: {e}")
            return False
    
    async def discover_target_accounts(self, campaign_id: int, max_accounts: int = 100) -> List[Dict[str, Any]]:
        """Discover target accounts for a campaign"""
        try:
            campaign = self.db_manager.session.query(OutreachCampaign).filter_by(id=campaign_id).first()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return []
            
            # Search for accounts using keywords related to the target industry
            industry_keywords = self._get_industry_keywords(campaign.target_industry)
            location_keywords = [campaign.target_location] if campaign.target_location else []
            
            all_keywords = industry_keywords + location_keywords
            
            # Discover accounts
            discovered_accounts = await self.instagram_client.search_accounts_by_keywords(
                keywords=all_keywords,
                location=campaign.target_location,
                max_results=max_accounts
            )
            
            # Filter and save accounts
            saved_accounts = []
            for account in discovered_accounts:
                if self._should_target_account(account, campaign):
                    # Save to database
                    target_account = self.db_manager.add_target_account(
                        username=account['username'],
                        full_name=account['full_name'],
                        bio=account['bio'],
                        follower_count=account['follower_count'],
                        following_count=account['following_count'],
                        post_count=account['post_count'],
                        is_verified=account['is_verified'],
                        is_business=account['is_business'],
                        category=campaign.target_industry,
                        location=account['location'],
                        status='pending'
                    )
                    saved_accounts.append(target_account)
            
            # Update campaign with discovered accounts count
            campaign.accounts_targeted = len(saved_accounts)
            self.db_manager.session.commit()
            
            logger.info(f"Discovered {len(saved_accounts)} target accounts for campaign {campaign_id}")
            return saved_accounts
            
        except Exception as e:
            logger.error(f"Error discovering target accounts: {e}")
            return []
    
    async def execute_outreach_batch(self, campaign_id: int, batch_size: int = 10) -> Dict[str, int]:
        """Execute outreach to a batch of target accounts"""
        try:
            campaign = self.db_manager.session.query(OutreachCampaign).filter_by(id=campaign_id).first()
            if not campaign:
                return {"success": 0, "failed": 0, "skipped": 0}
            
            # Get pending target accounts
            target_accounts = self.db_manager.get_target_accounts(
                industry=campaign.target_industry,
                location=campaign.target_location,
                status='pending'
            )[:batch_size]
            
            results = {"success": 0, "failed": 0, "skipped": 0}
            
            for account in target_accounts:
                try:
                    # Check if we should skip this account
                    if self._should_skip_account(account):
                        results["skipped"] += 1
                        continue
                    
                    # Get account details from Instagram
                    account_info = await self.instagram_client.get_account_info(account.username)
                    if not account_info:
                        results["failed"] += 1
                        continue
                    
                    # Generate personalized message
                    message = self.ai_system.generate_outreach_message(account_info)
                    
                    # Send DM
                    success = await self.instagram_client.send_dm(account_info['user_id'], message)
                    
                    if success:
                        # Update account status
                        self.db_manager.update_target_account(
                            account.username,
                            status='contacted',
                            last_contacted=datetime.utcnow(),
                            contact_attempts=account.contact_attempts + 1
                        )
                        results["success"] += 1
                        
                        # Add delay between messages
                        await asyncio.sleep(settings.min_delay_between_messages)
                    else:
                        results["failed"] += 1
                    
                except Exception as e:
                    logger.error(f"Error contacting account {account.username}: {e}")
                    results["failed"] += 1
                
                # Add random delay to appear more human-like
                await asyncio.sleep(random.randint(30, 120))
            
            # Update campaign statistics
            campaign.responses_received += results["success"]
            self.db_manager.session.commit()
            
            logger.info(f"Outreach batch completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error executing outreach batch: {e}")
            return {"success": 0, "failed": 0, "skipped": 0}
    
    async def engage_with_account(self, username: str) -> bool:
        """Engage with an account (like posts, follow)"""
        try:
            account_info = await self.instagram_client.get_account_info(username)
            if not account_info:
                return False
            
            # Follow the account
            await self.instagram_client.follow_account(account_info['user_id'])
            
            # Like recent posts
            liked_count = await self.instagram_client.like_recent_posts(username, max_posts=3)
            
            logger.info(f"Engaged with {username}: followed and liked {liked_count} posts")
            return True
            
        except Exception as e:
            logger.error(f"Error engaging with account {username}: {e}")
            return False
    
    async def monitor_responses(self) -> List[Dict[str, Any]]:
        """Monitor for responses to outreach messages"""
        try:
            # Get unread DMs
            unread_dms = await self.instagram_client.get_unread_dms()
            responses = []
            
            for dm in unread_dms:
                # Check if this is a response to our outreach
                if self._is_outreach_response(dm):
                    responses.append({
                        'username': dm['username'],
                        'content': dm['content'],
                        'timestamp': dm['timestamp'],
                        'thread_id': dm['thread_id']
                    })
                    
                    # Update account status
                    self.db_manager.update_target_account(
                        dm['username'],
                        status='responded'
                    )
            
            return responses
            
        except Exception as e:
            logger.error(f"Error monitoring responses: {e}")
            return []
    
    def _get_industry_keywords(self, industry: str) -> List[str]:
        """Get relevant keywords for an industry"""
        keyword_map = {
            'real_estate': [
                'real estate', 'property', 'realtor', 'realty', 'homes', 'houses',
                'apartments', 'condos', 'villas', 'commercial property', 'real estate agent'
            ],
            'construction': [
                'construction', 'building', 'contractor', 'developer', 'construction company',
                'building contractor', 'construction services', 'general contractor'
            ],
            'architecture': [
                'architecture', 'architect', 'architectural design', 'building design',
                'interior design', 'landscape architecture', 'architectural firm'
            ]
        }
        
        return keyword_map.get(industry, [industry])
    
    def _get_default_template(self, industry: str) -> str:
        """Get default message template for an industry"""
        templates = {
            'real_estate': f"Hi! I love your real estate content! {settings.studio_name} specializes in professional photography and marketing for real estate professionals. Would love to discuss how we can help showcase your properties! 🏠✨",
            'construction': f"Hello! Your construction projects look amazing! {settings.studio_name} creates compelling visual content for construction companies. Let's discuss how we can help tell your story! 🏗️📸",
            'architecture': f"Hi there! Your architectural work is stunning! {settings.studio_name} specializes in architectural photography and design marketing. Would love to collaborate! 🏛️✨"
        }
        
        return templates.get(industry, f"Hi! I love your content! {settings.studio_name} specializes in creative services for businesses like yours. Let's discuss how we can help! ✨")
    
    def _should_target_account(self, account: Dict[str, Any], campaign: OutreachCampaign) -> bool:
        """Determine if an account should be targeted"""
        # Skip if already in database
        existing = self.db_manager.session.query(TargetAccount).filter_by(username=account['username']).first()
        if existing:
            return False
        
        # Skip private accounts
        if account.get('is_private', False):
            return False
        
        # Skip if follower count is too low or too high
        follower_count = account.get('follower_count', 0)
        if follower_count < 100 or follower_count > 100000:
            return False
        
        # Check if account is relevant to campaign
        bio = account.get('bio', '').lower()
        full_name = account.get('full_name', '').lower()
        
        industry_keywords = self._get_industry_keywords(campaign.target_industry)
        for keyword in industry_keywords:
            if keyword.lower() in bio or keyword.lower() in full_name:
                return True
        
        return False
    
    def _should_skip_account(self, account: TargetAccount) -> bool:
        """Determine if we should skip contacting an account"""
        # Skip if already contacted recently
        if account.last_contacted and account.last_contacted > datetime.utcnow() - timedelta(days=7):
            return True
        
        # Skip if too many contact attempts
        if account.contact_attempts >= 3:
            return True
        
        # Skip if account is blocked or not interested
        if account.status in ['blocked', 'not_interested']:
            return True
        
        return False
    
    def _is_outreach_response(self, dm: Dict[str, Any]) -> bool:
        """Check if a DM is a response to our outreach"""
        # This is a simplified check - in practice, you'd want to track conversation threads
        content = dm['content'].lower()
        
        # Look for response indicators
        response_indicators = [
            'thank you', 'thanks', 'interested', 'tell me more', 'pricing',
            'cost', 'services', 'portfolio', 'website', 'contact'
        ]
        
        return any(indicator in content for indicator in response_indicators)
    
    async def run_continuous_outreach(self, campaign_id: int):
        """Run continuous outreach for a campaign"""
        self.is_running = True
        
        while self.is_running:
            try:
                # Execute outreach batch
                results = await self.execute_outreach_batch(campaign_id, batch_size=5)
                
                # Monitor for responses
                responses = await self.monitor_responses()
                
                if responses:
                    logger.info(f"Received {len(responses)} responses")
                
                # Wait before next batch
                await asyncio.sleep(3600)  # Wait 1 hour between batches
                
            except Exception as e:
                logger.error(f"Error in continuous outreach: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
        
        logger.info("Continuous outreach stopped")
    
    def stop_outreach(self):
        """Stop continuous outreach"""
        self.is_running = False
