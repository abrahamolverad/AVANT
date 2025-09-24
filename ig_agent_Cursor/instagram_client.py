"""
Instagram API client for handling DMs and account interactions
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, SelectContactPointRecoveryForm
from config import settings

logger = logging.getLogger(__name__)

class InstagramClient:
    def __init__(self):
        self.client = Client()
        self.is_logged_in = False
        self.rate_limit_tracker = {
            'dms_sent': 0,
            'last_dm_reset': datetime.now(),
            'outreach_sent': 0,
            'last_outreach_reset': datetime.now()
        }
    
    async def login(self) -> bool:
        """Login to Instagram"""
        try:
            # Try to load existing session first
            try:
                self.client.load_settings(f"session_{settings.instagram_username}.json")
                self.client.login(settings.instagram_username, settings.instagram_password)
                self.is_logged_in = True
                logger.info("Successfully logged in with existing session")
                return True
            except:
                # If loading session fails, do fresh login
                pass
            
            # Fresh login
            self.client.login(settings.instagram_username, settings.instagram_password)
            
            # Save session for future use
            self.client.dump_settings(f"session_{settings.instagram_username}.json")
            self.is_logged_in = True
            logger.info("Successfully logged in to Instagram")
            return True
            
        except ChallengeRequired as e:
            logger.error(f"Challenge required: {e}")
            return False
        except SelectContactPointRecoveryForm as e:
            logger.error(f"Account recovery required: {e}")
            return False
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def get_unread_dms(self) -> List[Dict[str, Any]]:
        """Get unread direct messages"""
        if not self.is_logged_in:
            await self.login()
        
        try:
            threads = self.client.direct_threads()
            unread_dms = []
            
            for thread in threads:
                if thread.messages and not thread.messages[0].is_from_me:
                    # Get the latest message
                    latest_message = thread.messages[0]
                    
                    # Check if we haven't responded to this message
                    if not self._has_responded_to_message(thread, latest_message):
                        unread_dms.append({
                            'thread_id': thread.id,
                            'user_id': thread.users[0].pk if thread.users else None,
                            'username': thread.users[0].username if thread.users else 'unknown',
                            'message_id': latest_message.id,
                            'content': latest_message.text or '',
                            'message_type': latest_message.item_type,
                            'timestamp': latest_message.timestamp,
                            'is_read': latest_message.is_read
                        })
            
            return unread_dms
            
        except Exception as e:
            logger.error(f"Error getting unread DMs: {e}")
            return []
    
    async def send_dm(self, user_id: str, message: str) -> bool:
        """Send a direct message to a user"""
        if not self.is_logged_in:
            await self.login()
        
        # Check rate limits
        if not self._check_rate_limit('dms'):
            logger.warning("Rate limit exceeded for DMs")
            return False
        
        try:
            self.client.direct_send(message, user_ids=[user_id])
            self.rate_limit_tracker['dms_sent'] += 1
            logger.info(f"DM sent to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending DM: {e}")
            return False
    
    async def search_accounts_by_keywords(self, keywords: List[str], location: str = None, 
                                        max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for accounts by keywords and location"""
        if not self.is_logged_in:
            await self.login()
        
        try:
            accounts = []
            
            for keyword in keywords:
                # Search by hashtag
                hashtag = self.client.hashtag_info(keyword.replace(' ', ''))
                recent_media = self.client.hashtag_medias_recent(keyword.replace(' ', ''), amount=20)
                
                for media in recent_media:
                    user = media.user
                    if self._is_relevant_account(user, location):
                        accounts.append({
                            'username': user.username,
                            'full_name': user.full_name,
                            'user_id': user.pk,
                            'bio': user.biography,
                            'follower_count': user.follower_count,
                            'following_count': user.following_count,
                            'post_count': user.media_count,
                            'is_verified': user.is_verified,
                            'is_business': user.is_business,
                            'is_private': user.is_private,
                            'external_url': user.external_url,
                            'location': self._extract_location_from_bio(user.biography),
                            'category': self._categorize_account(user.biography, user.full_name),
                            'last_activity': media.taken_at if hasattr(media, 'taken_at') else None
                        })
            
            # Remove duplicates and sort by follower count
            unique_accounts = {}
            for account in accounts:
                if account['username'] not in unique_accounts:
                    unique_accounts[account['username']] = account
                elif account['follower_count'] > unique_accounts[account['username']]['follower_count']:
                    unique_accounts[account['username']] = account
            
            return list(unique_accounts.values())[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching accounts: {e}")
            return []
    
    async def get_account_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific account"""
        if not self.is_logged_in:
            await self.login()
        
        try:
            user = self.client.user_info_by_username(username)
            return {
                'username': user.username,
                'full_name': user.full_name,
                'user_id': user.pk,
                'bio': user.biography,
                'follower_count': user.follower_count,
                'following_count': user.following_count,
                'post_count': user.media_count,
                'is_verified': user.is_verified,
                'is_business': user.is_business,
                'is_private': user.is_private,
                'external_url': user.external_url,
                'profile_pic_url': user.profile_pic_url,
                'location': self._extract_location_from_bio(user.biography),
                'category': self._categorize_account(user.biography, user.full_name)
            }
            
        except Exception as e:
            logger.error(f"Error getting account info for {username}: {e}")
            return None
    
    async def follow_account(self, user_id: str) -> bool:
        """Follow an account"""
        if not self.is_logged_in:
            await self.login()
        
        try:
            self.client.user_follow(user_id)
            logger.info(f"Followed user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error following user {user_id}: {e}")
            return False
    
    async def like_recent_posts(self, username: str, max_posts: int = 3) -> int:
        """Like recent posts from an account"""
        if not self.is_logged_in:
            await self.login()
        
        try:
            user_id = self.client.user_id_from_username(username)
            recent_media = self.client.user_medias(user_id, amount=max_posts)
            
            liked_count = 0
            for media in recent_media:
                try:
                    self.client.media_like(media.id)
                    liked_count += 1
                    time.sleep(2)  # Be respectful with likes
                except Exception as e:
                    logger.warning(f"Could not like post {media.id}: {e}")
            
            logger.info(f"Liked {liked_count} posts from {username}")
            return liked_count
            
        except Exception as e:
            logger.error(f"Error liking posts from {username}: {e}")
            return 0
    
    def _has_responded_to_message(self, thread, message) -> bool:
        """Check if we've already responded to a message"""
        # This is a simplified check - in practice, you'd want to track this in your database
        return False
    
    def _check_rate_limit(self, action_type: str) -> bool:
        """Check if we're within rate limits"""
        now = datetime.now()
        
        if action_type == 'dms':
            # Reset counter if it's been more than an hour
            if now - self.rate_limit_tracker['last_dm_reset'] > timedelta(hours=1):
                self.rate_limit_tracker['dms_sent'] = 0
                self.rate_limit_tracker['last_dm_reset'] = now
            
            return self.rate_limit_tracker['dms_sent'] < settings.max_dm_per_hour
        
        elif action_type == 'outreach':
            # Reset counter if it's been more than a day
            if now - self.rate_limit_tracker['last_outreach_reset'] > timedelta(days=1):
                self.rate_limit_tracker['outreach_sent'] = 0
                self.rate_limit_tracker['last_outreach_reset'] = now
            
            return self.rate_limit_tracker['outreach_sent'] < settings.max_outreach_per_day
        
        return True
    
    def _is_relevant_account(self, user, location: str = None) -> bool:
        """Check if an account is relevant to our targeting criteria"""
        bio = user.biography.lower()
        full_name = user.full_name.lower()
        
        # Check for target keywords
        for keyword in settings.target_keywords:
            if keyword.lower() in bio or keyword.lower() in full_name:
                return True
        
        # Check for target industries
        for industry in settings.target_industries:
            if industry.lower() in bio or industry.lower() in full_name:
                return True
        
        # Check for location
        if location:
            if location.lower() in bio or location.lower() in full_name:
                return True
        
        return False
    
    def _extract_location_from_bio(self, bio: str) -> Optional[str]:
        """Extract location information from bio"""
        bio_lower = bio.lower()
        for location in settings.target_locations:
            if location.lower() in bio_lower:
                return location
        return None
    
    def _categorize_account(self, bio: str, full_name: str) -> str:
        """Categorize account based on bio and name"""
        text = f"{bio} {full_name}".lower()
        
        if any(keyword in text for keyword in ['real estate', 'property', 'realtor', 'realty']):
            return 'real_estate'
        elif any(keyword in text for keyword in ['construction', 'building', 'developer']):
            return 'construction'
        elif any(keyword in text for keyword in ['architecture', 'architect', 'design']):
            return 'architecture'
        else:
            return 'other'
    
    def logout(self):
        """Logout from Instagram"""
        try:
            self.client.logout()
            self.is_logged_in = False
            logger.info("Logged out from Instagram")
        except Exception as e:
            logger.error(f"Error during logout: {e}")
