"""
AI Advisor Module
Handles interactions with Google's Gemini AI to generate portfolio insights.
"""

import os
import json
import logging
from typing import Dict, List, Optional
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAdvisor:
    """
    Manages interactions with Gemini AI Model for investment advice.
    """
    
    DEFAULT_MODEL = "gemini-1.5-pro" # Fallback
    PREFERRED_MODEL = "gemini-3-pro-preview" # Latest model

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro-latest"):
        """
        Initialize the AI Advisor.
        
        Args:
            api_key: Google Generative AI API Key
            model_name: Model version to use (e.g. 'gemini-1.5-pro', 'gemini-3.0-pro')
        """
        self.api_key = api_key
        self.model_name = model_name
        self._configure_api()
        
    def _configure_api(self):
        """Configure the Gemini API with provided key"""
        if not self.api_key:
            logger.warning("No API Key provided for AI Advisor")
            return
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}")
            self.model = None

    def generate_portfolio_summary(self, 
                                 portfolio_context: Dict, 
                                 market_analysis: List[Dict]) -> Dict[str, str]:
        """
        Generate an executive summary and strategy based on portfolio state.
        
        Args:
            portfolio_context: Dict containing total value, asset breakdown, P&L
            market_analysis: List of technical analysis for assets
            
        Returns:
            Dict containing 'title', 'text', 'mood' (bullish/bearish/neutral)
        """
        if not self.model:
            return None

        # Construct the prompt
        prompt = self._construct_prompt(portfolio_context, market_analysis)
        
        try:
            # Generate response
            response = self.model.generate_content(prompt)
            
            # Parse response (expecting JSON structure in text)
            # using heuristic parsing or instructing model to output JSON
            return self._parse_response(response.text)
            
        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            return None

    def _construct_prompt(self, portfolio: Dict, analysis: List[Dict]) -> str:
        """Construct the prompt for the LLM"""
        return f"""
        You are an expert crypto portfolio manager AI. app_name: "AntiGravity".
        Analyze the following portfolio and market data and provide a strategic executive summary.
        
        PORTFOLIO STATE:
        Total Value: ${portfolio.get('total_value', 0):,.2f}
        Unrealized P&L: ${portfolio.get('total_pnl', 0):,.2f}
        
        HOLDINGS:
        {json.dumps(portfolio.get('assets', []), indent=2)}
        
        TECHNICAL ANALYSIS:
        {json.dumps(analysis, indent=2)}
        
        TASK:
        1. Determine the overall strategy mode (e.g., "Accumulation", "Profit Taking", "Defensive", "Rebalancing").
        2. Write a concise, actionable summary (max 2-3 sentences).
        3. Identify the "market mood" (bullish, bearish, cautious, neutral).
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "title": "Strategy Mode Name",
            "text": "Concise summary text...",
            "mood": "bullish|bearish|cautious|neutral",
            "total_buy": 0.0,
            "total_sell": 0.0
        }}
        """

    def _parse_response(self, response_text: str) -> Dict:
        """Safe parsing of LLM response"""
        try:
            # Strip markdown code blocks if present
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            return data
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON")
            return {
                "title": "Analysis Complete",
                "text": response_text[:150] + "...", # Fallback to raw text
                "mood": "neutral"
            }

    def get_chat_response(self, message: str, portfolio_context: Dict, market_analysis: List[Dict]) -> str:
        """
        Generate a chat response based on user message and portfolio context.
        """
        if not self.model:
            return "I'm not connected to Gemini right now. Please check your API key settings."

        # specific prompt for chat
        prompt = f"""
        You are an expert crypto portfolio assistant named "AntiGravity".
        
        CONTEXT:
        Total Value: ${portfolio_context.get('total_value', 0):,.2f}
        Unrealized P&L: ${portfolio_context.get('total_pnl', 0):,.2f}
        
        ASSETS:
        {json.dumps(portfolio_context.get('assets', []), indent=2)}
        
        MARKET ANALYSIS:
        {json.dumps(market_analysis, indent=2)}
        
        USER QUESTION:
        {message}
        
        INSTRUCTIONS:
        - Answer the user's question directly using the provided portfolio data.
        - Be concise, helpful, and friendly.
        - If the user asks about an asset you don't hold, mention that.
        - Provide specific numbers (prices, pnl, etc) from the context.
        - Do not structure as JSON. Return plain text/markdown.
        """

        try:
            # Recommended settings for Gemini 3
            gen_config = genai.types.GenerationConfig(
                temperature=1.0, 
                candidate_count=1
            )
            
            logger.info("Sending chat request to Gemini 3...")
            response = self.model.generate_content(
                prompt,
                generation_config=gen_config
            )
            
            # Check if response has text, sometimes it might be blocked or empty
            if not response.text:
                return "I couldn't generate a response. Please try rephrasing."
            return response.text
        except Exception as e:
            logger.error(f"Chat generation error: {e}")
            return "Sorry, I encountered an error answering that. Please try again."
