"""
Conversation Manager for handling DM conversations and context tracking
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from database import DatabaseManager, Conversation, Message
from ai_response_system import AIResponseSystem
from instagram_client import InstagramClient
from config import settings

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.ai_system = AIResponseSystem()
        self.instagram_client = InstagramClient()
        self.active_conversations = {}
    
    async def process_incoming_dm(self, dm_data: Dict[str, Any]) -> Optional[str]:
        """Process an incoming DM and generate a response"""
        try:
            username = dm_data['username']
            user_id = dm_data['user_id']
            content = dm_data['content']
            thread_id = dm_data['thread_id']
            
            # Get or create conversation
            conversation = self.db_manager.get_conversation(user_id)
            if not conversation:
                conversation = self.db_manager.create_conversation(
                    instagram_user_id=user_id,
                    username=username,
                    context={'last_interaction': datetime.utcnow().isoformat()}
                )
            
            # Add message to database
            message = self.db_manager.add_message(
                conversation_id=conversation.id,
                instagram_message_id=dm_data['message_id'],
                sender_username=username,
                content=content,
                message_type=dm_data.get('message_type', 'text'),
                is_from_agent=False
            )
            
            # Analyze message sentiment and intent
            analysis = self.ai_system.analyze_message_sentiment(content)
            
            # Update conversation context
            context = conversation.conversation_context or {}
            context.update({
                'last_message': content,
                'last_analysis': analysis,
                'last_interaction': datetime.utcnow().isoformat(),
                'message_count': context.get('message_count', 0) + 1
            })
            
            # Check if this is a response to outreach
            if self._is_outreach_response(content, context):
                context['is_outreach_response'] = True
                context['outreach_stage'] = self._determine_outreach_stage(content, context)
            
            self.db_manager.update_conversation_context(conversation.id, context)
            
            # Generate response
            response = await self._generate_contextual_response(content, context, analysis)
            
            if response:
                # Send response
                success = await self.instagram_client.send_dm(user_id, response)
                
                if success:
                    # Save response to database
                    self.db_manager.add_message(
                        conversation_id=conversation.id,
                        instagram_message_id=f"response_{datetime.utcnow().timestamp()}",
                        sender_username=settings.instagram_username,
                        content=response,
                        is_from_agent=True
                    )
                    
                    # Update context with response
                    context['last_response'] = response
                    context['response_time'] = datetime.utcnow().isoformat()
                    self.db_manager.update_conversation_context(conversation.id, context)
                    
                    logger.info(f"Response sent to {username}: {response[:50]}...")
                    return response
                else:
                    logger.error(f"Failed to send response to {username}")
                    return None
            else:
                logger.warning(f"No response generated for {username}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing incoming DM: {e}")
            return None
    
    async def _generate_contextual_response(self, content: str, context: Dict[str, Any], 
                                          analysis: Dict[str, Any]) -> Optional[str]:
        """Generate a contextual response based on conversation history and analysis"""
        try:
            # Check if we should respond based on settings
            if not settings.enable_auto_response:
                return None
            
            # Check if this is a high-priority message
            if analysis.get('urgency') == 'high':
                return self.ai_system.generate_dm_response(content, context)
            
            # Check conversation history for context
            message_count = context.get('message_count', 0)
            is_outreach_response = context.get('is_outreach_response', False)
            
            # Build context for AI
            conversation_context = self._build_conversation_context(context)
            
            # Generate response using AI
            if is_outreach_response:
                # Use specialized outreach response logic
                response = await self._generate_outreach_response(content, context, conversation_context)
            else:
                # Use general DM response
                response = self.ai_system.generate_dm_response(content, context)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating contextual response: {e}")
            return None
    
    async def _generate_outreach_response(self, content: str, context: Dict[str, Any], 
                                        conversation_context: str) -> str:
        """Generate specialized response for outreach conversations"""
        try:
            # Determine the stage of the outreach conversation
            stage = context.get('outreach_stage', 'initial')
            
            if stage == 'initial_interest':
                return self._handle_initial_interest(content, context)
            elif stage == 'pricing_inquiry':
                return self._handle_pricing_inquiry(content, context)
            elif stage == 'portfolio_request':
                return self._handle_portfolio_request(content, context)
            elif stage == 'meeting_request':
                return self._handle_meeting_request(content, context)
            else:
                return self.ai_system.generate_dm_response(content, context)
                
        except Exception as e:
            logger.error(f"Error generating outreach response: {e}")
            return self.ai_system.generate_dm_response(content, context)
    
    def _handle_initial_interest(self, content: str, context: Dict[str, Any]) -> str:
        """Handle initial interest in services"""
        return f"Hi! Thanks for your interest! 😊 {settings.studio_name} specializes in professional creative services for real estate. We offer photography, videography, and marketing materials. Would you like to see some of our work? Check out {settings.studio_website} or I can send you some examples! ✨"
    
    def _handle_pricing_inquiry(self, content: str, context: Dict[str, Any]) -> str:
        """Handle pricing inquiries"""
        return f"Great question! Our pricing varies based on project scope and requirements. For a detailed quote, I'd love to learn more about your specific needs. Could you tell me about your project? In the meantime, you can see our portfolio at {settings.studio_website} 📸"
    
    def _handle_portfolio_request(self, content: str, context: Dict[str, Any]) -> str:
        """Handle portfolio requests"""
        return f"Absolutely! You can see our full portfolio at {settings.studio_website} 📸 We specialize in real estate photography, property videos, and marketing materials. I can also send you some specific examples if you tell me what type of project you have in mind! ✨"
    
    def _handle_meeting_request(self, content: str, context: Dict[str, Any]) -> str:
        """Handle meeting requests"""
        return f"That sounds great! I'd love to discuss your project in detail. You can reach us at {settings.studio_email} to schedule a consultation, or we can continue chatting here. What's the best way to reach you? 📞"
    
    def _is_outreach_response(self, content: str, context: Dict[str, Any]) -> bool:
        """Check if this is a response to our outreach"""
        content_lower = content.lower()
        
        # Look for response indicators
        response_indicators = [
            'thank you', 'thanks', 'interested', 'tell me more', 'pricing',
            'cost', 'services', 'portfolio', 'website', 'contact', 'hello',
            'hi', 'hey', 'sounds good', 'looks great'
        ]
        
        return any(indicator in content_lower for indicator in response_indicators)
    
    def _determine_outreach_stage(self, content: str, context: Dict[str, Any]) -> str:
        """Determine the stage of the outreach conversation"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['pricing', 'cost', 'price', 'how much']):
            return 'pricing_inquiry'
        elif any(word in content_lower for word in ['portfolio', 'work', 'examples', 'samples']):
            return 'portfolio_request'
        elif any(word in content_lower for word in ['meeting', 'call', 'discuss', 'talk']):
            return 'meeting_request'
        elif any(word in content_lower for word in ['interested', 'tell me more', 'sounds good']):
            return 'initial_interest'
        else:
            return 'initial'
    
    def _build_conversation_context(self, context: Dict[str, Any]) -> str:
        """Build conversation context string for AI"""
        context_parts = []
        
        if context.get('last_message'):
            context_parts.append(f"Last message: {context['last_message']}")
        
        if context.get('last_response'):
            context_parts.append(f"Last response: {context['last_response']}")
        
        if context.get('message_count'):
            context_parts.append(f"Message count: {context['message_count']}")
        
        if context.get('is_outreach_response'):
            context_parts.append("This is a response to our outreach")
        
        if context.get('outreach_stage'):
            context_parts.append(f"Outreach stage: {context['outreach_stage']}")
        
        return " | ".join(context_parts)
    
    async def get_conversation_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a summary of a conversation"""
        try:
            conversation = self.db_manager.get_conversation(user_id)
            if not conversation:
                return {}
            
            # Get recent messages
            messages = self.db_manager.session.query(Message).filter_by(
                conversation_id=conversation.id
            ).order_by(Message.created_at.desc()).limit(10).all()
            
            return {
                'username': conversation.username,
                'message_count': len(messages),
                'last_interaction': conversation.last_message_time,
                'context': conversation.conversation_context,
                'recent_messages': [
                    {
                        'content': msg.content,
                        'is_from_agent': msg.is_from_agent,
                        'timestamp': msg.created_at
                    }
                    for msg in reversed(messages)
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return {}
    
    async def mark_conversation_inactive(self, user_id: str):
        """Mark a conversation as inactive"""
        try:
            conversation = self.db_manager.get_conversation(user_id)
            if conversation:
                conversation.is_active = False
                self.db_manager.session.commit()
                logger.info(f"Marked conversation with {conversation.username} as inactive")
        except Exception as e:
            logger.error(f"Error marking conversation inactive: {e}")
    
    async def get_active_conversations(self) -> List[Dict[str, Any]]:
        """Get all active conversations"""
        try:
            conversations = self.db_manager.session.query(Conversation).filter_by(
                is_active=True
            ).all()
            
            return [
                {
                    'user_id': conv.instagram_user_id,
                    'username': conv.username,
                    'last_message_time': conv.last_message_time,
                    'message_count': conv.conversation_context.get('message_count', 0) if conv.conversation_context else 0,
                    'is_outreach_response': conv.conversation_context.get('is_outreach_response', False) if conv.conversation_context else False
                }
                for conv in conversations
            ]
            
        except Exception as e:
            logger.error(f"Error getting active conversations: {e}")
            return []
