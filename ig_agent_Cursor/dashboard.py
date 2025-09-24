"""
Web Dashboard for Instagram AI Agent monitoring and configuration
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for
import json
import asyncio
from datetime import datetime, timedelta
from database import DatabaseManager, Conversation, Message, TargetAccount, OutreachCampaign
from config import settings
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Global database manager
db_manager = None

def init_database():
    """Initialize database connection"""
    global db_manager
    db_manager = DatabaseManager(settings.database_url)

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        # Get statistics
        stats = get_dashboard_stats()
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return f"Error loading dashboard: {e}", 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    try:
        stats = get_dashboard_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/conversations')
def conversations():
    """Conversations page"""
    try:
        conversations = get_conversations()
        return render_template('conversations.html', conversations=conversations)
    except Exception as e:
        logger.error(f"Error loading conversations: {e}")
        return f"Error loading conversations: {e}", 500

@app.route('/api/conversations')
def api_conversations():
    """API endpoint for conversations"""
    try:
        conversations = get_conversations()
        return jsonify(conversations)
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/conversations/<int:conversation_id>')
def conversation_detail(conversation_id):
    """Conversation detail page"""
    try:
        conversation = get_conversation_detail(conversation_id)
        if not conversation:
            return "Conversation not found", 404
        return render_template('conversation_detail.html', conversation=conversation)
    except Exception as e:
        logger.error(f"Error loading conversation detail: {e}")
        return f"Error loading conversation detail: {e}", 500

@app.route('/campaigns')
def campaigns():
    """Campaigns page"""
    try:
        campaigns = get_campaigns()
        return render_template('campaigns.html', campaigns=campaigns)
    except Exception as e:
        logger.error(f"Error loading campaigns: {e}")
        return f"Error loading campaigns: {e}", 500

@app.route('/api/campaigns')
def api_campaigns():
    """API endpoint for campaigns"""
    try:
        campaigns = get_campaigns()
        return jsonify(campaigns)
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/campaigns/create', methods=['GET', 'POST'])
def create_campaign():
    """Create new campaign"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            campaign = db_manager.create_outreach_campaign(
                name=data['name'],
                target_industry=data['target_industry'],
                target_location=data['target_location'],
                message_template=data.get('message_template', '')
            )
            return jsonify({'success': True, 'campaign_id': campaign.id})
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            return jsonify({'error': str(e)}), 500
    
    return render_template('create_campaign.html')

@app.route('/targets')
def targets():
    """Target accounts page"""
    try:
        targets = get_target_accounts()
        return render_template('targets.html', targets=targets)
    except Exception as e:
        logger.error(f"Error loading targets: {e}")
        return f"Error loading targets: {e}", 500

@app.route('/api/targets')
def api_targets():
    """API endpoint for target accounts"""
    try:
        targets = get_target_accounts()
        return jsonify(targets)
    except Exception as e:
        logger.error(f"Error getting targets: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/settings')
def settings_page():
    """Settings page"""
    try:
        return render_template('settings.html', settings=settings.__dict__)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return f"Error loading settings: {e}", 500

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """API endpoint for settings"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            # Update settings (you'd want to implement this properly)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify(settings.__dict__)

def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Get conversation stats
        total_conversations = db_manager.session.query(Conversation).count()
        active_conversations = db_manager.session.query(Conversation).filter_by(is_active=True).count()
        
        # Get message stats
        total_messages = db_manager.session.query(Message).count()
        agent_messages = db_manager.session.query(Message).filter_by(is_from_agent=True).count()
        
        # Get campaign stats
        total_campaigns = db_manager.session.query(OutreachCampaign).count()
        active_campaigns = db_manager.session.query(OutreachCampaign).filter_by(status='active').count()
        
        # Get target account stats
        total_targets = db_manager.session.query(TargetAccount).count()
        contacted_targets = db_manager.session.query(TargetAccount).filter_by(status='contacted').count()
        responded_targets = db_manager.session.query(TargetAccount).filter_by(status='responded').count()
        
        # Get recent activity
        recent_messages = db_manager.session.query(Message).order_by(
            Message.created_at.desc()
        ).limit(10).all()
        
        return {
            'conversations': {
                'total': total_conversations,
                'active': active_conversations
            },
            'messages': {
                'total': total_messages,
                'agent_sent': agent_messages,
                'received': total_messages - agent_messages
            },
            'campaigns': {
                'total': total_campaigns,
                'active': active_campaigns
            },
            'targets': {
                'total': total_targets,
                'contacted': contacted_targets,
                'responded': responded_targets,
                'conversion_rate': (responded_targets / contacted_targets * 100) if contacted_targets > 0 else 0
            },
            'recent_activity': [
                {
                    'type': 'message',
                    'content': msg.content[:50] + '...' if len(msg.content) > 50 else msg.content,
                    'sender': msg.sender_username,
                    'timestamp': msg.created_at.isoformat(),
                    'is_from_agent': msg.is_from_agent
                }
                for msg in recent_messages
            ]
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return {}

def get_conversations():
    """Get all conversations"""
    try:
        conversations = db_manager.session.query(Conversation).order_by(
            Conversation.last_message_time.desc()
        ).all()
        
        return [
            {
                'id': conv.id,
                'username': conv.username,
                'user_id': conv.instagram_user_id,
                'last_message_time': conv.last_message_time.isoformat(),
                'is_active': conv.is_active,
                'message_count': conv.conversation_context.get('message_count', 0) if conv.conversation_context else 0,
                'is_outreach_response': conv.conversation_context.get('is_outreach_response', False) if conv.conversation_context else False
            }
            for conv in conversations
        ]
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return []

def get_conversation_detail(conversation_id):
    """Get detailed conversation information"""
    try:
        conversation = db_manager.session.query(Conversation).filter_by(id=conversation_id).first()
        if not conversation:
            return None
        
        messages = db_manager.session.query(Message).filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at.asc()).all()
        
        return {
            'id': conversation.id,
            'username': conversation.username,
            'user_id': conversation.instagram_user_id,
            'is_active': conversation.is_active,
            'context': conversation.conversation_context,
            'messages': [
                {
                    'id': msg.id,
                    'content': msg.content,
                    'sender': msg.sender_username,
                    'timestamp': msg.created_at.isoformat(),
                    'is_from_agent': msg.is_from_agent,
                    'message_type': msg.message_type
                }
                for msg in messages
            ]
        }
    except Exception as e:
        logger.error(f"Error getting conversation detail: {e}")
        return None

def get_campaigns():
    """Get all campaigns"""
    try:
        campaigns = db_manager.session.query(OutreachCampaign).order_by(
            OutreachCampaign.created_at.desc()
        ).all()
        
        return [
            {
                'id': camp.id,
                'name': camp.name,
                'target_industry': camp.target_industry,
                'target_location': camp.target_location,
                'status': camp.status,
                'accounts_targeted': camp.accounts_targeted,
                'responses_received': camp.responses_received,
                'conversions': camp.conversions,
                'created_at': camp.created_at.isoformat(),
                'updated_at': camp.updated_at.isoformat()
            }
            for camp in campaigns
        ]
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        return []

def get_target_accounts():
    """Get all target accounts"""
    try:
        targets = db_manager.session.query(TargetAccount).order_by(
            TargetAccount.created_at.desc()
        ).all()
        
        return [
            {
                'id': target.id,
                'username': target.username,
                'full_name': target.full_name,
                'bio': target.bio,
                'follower_count': target.follower_count,
                'following_count': target.following_count,
                'post_count': target.post_count,
                'is_verified': target.is_verified,
                'is_business': target.is_business,
                'category': target.category,
                'location': target.location,
                'status': target.status,
                'contact_attempts': target.contact_attempts,
                'last_contacted': target.last_contacted.isoformat() if target.last_contacted else None,
                'created_at': target.created_at.isoformat()
            }
            for target in targets
        ]
    except Exception as e:
        logger.error(f"Error getting target accounts: {e}")
        return []

if __name__ == '__main__':
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
