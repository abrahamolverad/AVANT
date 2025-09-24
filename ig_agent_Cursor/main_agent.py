"""
Main Instagram AI Agent - Orchestrates all components
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, Any, List
from database import DatabaseManager
from instagram_client import InstagramClient
from conversation_manager import ConversationManager
from outreach_manager import OutreachManager
from ai_response_system import AIResponseSystem
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class InstagramAIAgent:
    def __init__(self):
        self.db_manager = DatabaseManager(settings.database_url)
        self.instagram_client = InstagramClient()
        self.conversation_manager = ConversationManager(self.db_manager)
        self.outreach_manager = OutreachManager(self.db_manager)
        self.ai_system = AIResponseSystem()
        self.is_running = False
        self.tasks = []
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    async def start(self):
        """Start the Instagram AI Agent"""
        try:
            logger.info("Starting Instagram AI Agent...")
            
            # Login to Instagram
            if not await self.instagram_client.login():
                logger.error("Failed to login to Instagram. Exiting.")
                return False
            
            self.is_running = True
            
            # Start background tasks
            self.tasks = [
                asyncio.create_task(self._monitor_dms()),
                asyncio.create_task(self._monitor_outreach_responses()),
                asyncio.create_task(self._periodic_cleanup()),
            ]
            
            # Start outreach campaigns if enabled
            if settings.enable_auto_outreach:
                self.tasks.append(asyncio.create_task(self._run_outreach_campaigns()))
            
            logger.info("Instagram AI Agent started successfully")
            
            # Wait for all tasks
            await asyncio.gather(*self.tasks)
            
        except Exception as e:
            logger.error(f"Error starting Instagram AI Agent: {e}")
            return False
    
    async def stop(self):
        """Stop the Instagram AI Agent"""
        logger.info("Stopping Instagram AI Agent...")
        self.is_running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close database connection
        self.db_manager.close()
        
        # Logout from Instagram
        self.instagram_client.logout()
        
        logger.info("Instagram AI Agent stopped")
    
    async def _monitor_dms(self):
        """Monitor for incoming DMs and process them"""
        logger.info("Starting DM monitoring...")
        
        while self.is_running:
            try:
                # Get unread DMs
                unread_dms = await self.instagram_client.get_unread_dms()
                
                for dm in unread_dms:
                    logger.info(f"Processing DM from {dm['username']}: {dm['content'][:50]}...")
                    
                    # Process the DM
                    response = await self.conversation_manager.process_incoming_dm(dm)
                    
                    if response:
                        logger.info(f"Response sent to {dm['username']}")
                    else:
                        logger.warning(f"No response generated for {dm['username']}")
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring DMs: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _monitor_outreach_responses(self):
        """Monitor for responses to outreach messages"""
        logger.info("Starting outreach response monitoring...")
        
        while self.is_running:
            try:
                # Monitor for responses
                responses = await self.outreach_manager.monitor_responses()
                
                for response in responses:
                    logger.info(f"Outreach response from {response['username']}: {response['content'][:50]}...")
                    
                    # Process the response as a regular DM
                    dm_data = {
                        'username': response['username'],
                        'user_id': response.get('user_id', ''),
                        'content': response['content'],
                        'thread_id': response['thread_id'],
                        'message_id': f"outreach_response_{datetime.now().timestamp()}",
                        'message_type': 'text'
                    }
                    
                    await self.conversation_manager.process_incoming_dm(dm_data)
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error monitoring outreach responses: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _run_outreach_campaigns(self):
        """Run outreach campaigns"""
        logger.info("Starting outreach campaigns...")
        
        while self.is_running:
            try:
                # Get active campaigns
                campaigns = self.db_manager.session.query(self.db_manager.OutreachCampaign).filter_by(
                    status='active'
                ).all()
                
                for campaign in campaigns:
                    logger.info(f"Running outreach campaign: {campaign.name}")
                    
                    # Execute outreach batch
                    results = await self.outreach_manager.execute_outreach_batch(
                        campaign.id, batch_size=5
                    )
                    
                    logger.info(f"Campaign {campaign.name} results: {results}")
                
                # Wait before next batch
                await asyncio.sleep(3600)  # Wait 1 hour between batches
                
            except Exception as e:
                logger.error(f"Error running outreach campaigns: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error
    
    async def _periodic_cleanup(self):
        """Periodic cleanup tasks"""
        logger.info("Starting periodic cleanup...")
        
        while self.is_running:
            try:
                # Mark old conversations as inactive
                old_conversations = self.db_manager.session.query(
                    self.db_manager.Conversation
                ).filter(
                    self.db_manager.Conversation.last_message_time < 
                    datetime.utcnow() - timedelta(days=7)
                ).all()
                
                for conv in old_conversations:
                    conv.is_active = False
                
                self.db_manager.session.commit()
                
                logger.info(f"Marked {len(old_conversations)} conversations as inactive")
                
                # Wait 24 hours before next cleanup
                await asyncio.sleep(86400)
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop())
    
    async def create_outreach_campaign(self, name: str, target_industry: str, 
                                     target_location: str, message_template: str = None) -> bool:
        """Create a new outreach campaign"""
        try:
            success = await self.outreach_manager.start_outreach_campaign(
                name, target_industry, target_location, message_template
            )
            
            if success:
                logger.info(f"Created outreach campaign: {name}")
                
                # Discover target accounts
                campaign = self.db_manager.session.query(
                    self.db_manager.OutreachCampaign
                ).filter_by(name=name).first()
                
                if campaign:
                    await self.outreach_manager.discover_target_accounts(campaign.id)
                    logger.info(f"Discovered target accounts for campaign: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating outreach campaign: {e}")
            return False
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        try:
            # Get active conversations
            active_conversations = await self.conversation_manager.get_active_conversations()
            
            # Get campaign statistics
            campaigns = self.db_manager.session.query(self.db_manager.OutreachCampaign).all()
            
            # Get target account statistics
            target_accounts = self.db_manager.session.query(self.db_manager.TargetAccount).all()
            
            return {
                'is_running': self.is_running,
                'active_conversations': len(active_conversations),
                'total_campaigns': len(campaigns),
                'active_campaigns': len([c for c in campaigns if c.status == 'active']),
                'total_target_accounts': len(target_accounts),
                'contacted_accounts': len([a for a in target_accounts if a.status == 'contacted']),
                'responded_accounts': len([a for a in target_accounts if a.status == 'responded']),
                'last_update': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return {'error': str(e)}

async def main():
    """Main entry point"""
    agent = InstagramAIAgent()
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
