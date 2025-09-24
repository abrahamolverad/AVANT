"""
AI Response System for handling DM queries and generating outreach messages
"""
import openai
import anthropic
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging
from config import settings

logger = logging.getLogger(__name__)

class AIResponseSystem:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        
        # System prompts for different scenarios
        self.dm_response_prompt = f"""
        You are an AI assistant for {settings.studio_name}, a creative studio specializing in professional creative services.
        
        Studio Information:
        - Name: {settings.studio_name}
        - Description: {settings.studio_description}
        - Website: {settings.studio_website}
        - Email: {settings.studio_email}
        
        Your role is to respond to Instagram DMs in a friendly, professional, and helpful manner. You should:
        1. Be warm and engaging while maintaining professionalism
        2. Answer questions about services, pricing, and availability
        3. Guide potential clients to the website or email for detailed inquiries
        4. Show enthusiasm for creative projects
        5. Keep responses concise but informative
        6. Use emojis sparingly and appropriately
        7. Always be helpful and solution-oriented
        
        If you don't know something specific, politely direct them to the website or email for more detailed information.
        """
        
        self.outreach_prompt = f"""
        You are creating outreach messages for {settings.studio_name} to contact potential clients in the real estate industry.
        
        Studio Information:
        - Name: {settings.studio_name}
        - Description: {settings.studio_description}
        - Website: {settings.studio_website}
        - Email: {settings.studio_email}
        
        Create personalized, professional outreach messages that:
        1. Are warm and engaging, not salesy
        2. Show genuine interest in their business
        3. Highlight relevant creative services for real estate
        4. Include a clear call-to-action
        5. Are personalized based on their profile information
        6. Keep messages under 200 characters for Instagram
        7. Use appropriate emojis sparingly
        
        Focus on services like:
        - Real estate photography
        - Property marketing materials
        - Social media content creation
        - Brand development
        - Website design
        - Video production for properties
        """
    
    def generate_dm_response(self, message_content: str, conversation_context: Dict[str, Any] = None) -> str:
        """Generate a response to an incoming DM"""
        try:
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": self.dm_response_prompt},
                        {"role": "user", "content": f"Respond to this Instagram DM: {message_content}"}
                    ],
                    max_tokens=200,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
            
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=200,
                    temperature=0.7,
                    system=self.dm_response_prompt,
                    messages=[{"role": "user", "content": f"Respond to this Instagram DM: {message_content}"}]
                )
                return response.content[0].text.strip()
            
            else:
                return self._fallback_response(message_content)
                
        except Exception as e:
            logger.error(f"Error generating DM response: {e}")
            return self._fallback_response(message_content)
    
    def generate_outreach_message(self, target_account: Dict[str, Any]) -> str:
        """Generate a personalized outreach message for a target account"""
        try:
            # Extract relevant information from target account
            username = target_account.get('username', '')
            bio = target_account.get('bio', '')
            full_name = target_account.get('full_name', '')
            location = target_account.get('location', '')
            
            # Create personalized context
            personalization = f"""
            Target Account Information:
            - Username: @{username}
            - Full Name: {full_name}
            - Bio: {bio}
            - Location: {location}
            """
            
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": self.outreach_prompt},
                        {"role": "user", "content": f"{personalization}\n\nCreate a personalized outreach message for this account."}
                    ],
                    max_tokens=150,
                    temperature=0.8
                )
                return response.choices[0].message.content.strip()
            
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=150,
                    temperature=0.8,
                    system=self.outreach_prompt,
                    messages=[{"role": "user", "content": f"{personalization}\n\nCreate a personalized outreach message for this account."}]
                )
                return response.content[0].text.strip()
            
            else:
                return self._fallback_outreach_message(target_account)
                
        except Exception as e:
            logger.error(f"Error generating outreach message: {e}")
            return self._fallback_outreach_message(target_account)
    
    def analyze_message_sentiment(self, message_content: str) -> Dict[str, Any]:
        """Analyze the sentiment and intent of an incoming message"""
        try:
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Analyze the sentiment and intent of this Instagram message. Return a JSON object with 'sentiment' (positive/negative/neutral), 'intent' (inquiry/complaint/compliment/other), and 'urgency' (high/medium/low)."},
                        {"role": "user", "content": message_content}
                    ],
                    max_tokens=100,
                    temperature=0.3
                )
                return json.loads(response.choices[0].message.content.strip())
            else:
                return {"sentiment": "neutral", "intent": "other", "urgency": "low"}
        except Exception as e:
            logger.error(f"Error analyzing message sentiment: {e}")
            return {"sentiment": "neutral", "intent": "other", "urgency": "low"}
    
    def _fallback_response(self, message_content: str) -> str:
        """Fallback response when AI services are unavailable"""
        responses = [
            f"Hi! Thanks for reaching out to {settings.studio_name}! 😊 I'd love to help you with your creative project. For detailed information about our services, please visit {settings.studio_website} or email us at {settings.studio_email}.",
            f"Hello! Great to hear from you! {settings.studio_name} specializes in professional creative services. Check out our work at {settings.studio_website} or contact us at {settings.studio_email} for more details!",
            f"Hi there! Thanks for your interest in {settings.studio_name}! We'd be happy to discuss your creative needs. Visit {settings.studio_website} or email {settings.studio_email} for more information."
        ]
        return responses[hash(message_content) % len(responses)]
    
    def _fallback_outreach_message(self, target_account: Dict[str, Any]) -> str:
        """Fallback outreach message when AI services are unavailable"""
        username = target_account.get('username', 'there')
        return f"Hi @{username}! 👋 I love your content! {settings.studio_name} specializes in creative services for businesses like yours. Would love to discuss how we can help elevate your brand! Check us out: {settings.studio_website}"
