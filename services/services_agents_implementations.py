"""
services/agents/translator.py, stylist.py, quality_control.py
Concrete agent implementations with specialized prompts and logic
"""

from typing import Type, Optional, Any
from pydantic import BaseModel, Field
import logging

from services.services_agents_base import BaseAgent, AgentProvider, ValidationException
from schemas.schemas_translation import (
    TranslatorAgentOutput,
    StylistAgentOutput,
    QualityControlResult,
    QualityIssue,
    IssueType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# TRANSLATOR AGENT
# ============================================================================

class TranslatorAgent(BaseAgent):
    """
    Translates text from source language to target language.
    Focus: Accuracy, terminology preservation, context understanding.
    """
    
    def __init__(
        self,
        provider: AgentProvider = AgentProvider.ANTHROPIC,
        language_pair: str = "Georgian→English",
    ):
        super().__init__(
            name="translator",
            provider=provider,
            max_retries=3,
            timeout_seconds=30
        )
        self.language_pair = language_pair
    
    async def process(self, input_data: str, **kwargs) -> str:
        """
        Translate text from source to target language.
        
        Args:
            input_data: Text to translate
            source_language: Source language name
            target_language: Target language name
        """
        source_language = kwargs.get("source_language", "Georgian")
        target_language = kwargs.get("target_language", "English")
        context = kwargs.get("context", "")
        
        prompt = self._build_prompt(
            input_data,
            source_language,
            target_language,
            context
        )
        
        # Call LLM with structured output
        response = await self.call_llm(
            prompt,
            output_schema=TranslatorAgentOutput
        )
        
        return response
    
    def _build_prompt(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: str = "",
    ) -> str:
        """Construct translator prompt"""
        
        context_section = f"Context: {context}\n\n" if context else ""
        
        prompt = f"""You are an expert translator specializing in Georgian-English translation.

Your task is to translate the following text from {source_language} to {target_language}.

INSTRUCTIONS:
1. Preserve the exact meaning and nuance of the original text
2. Maintain formal/technical terminology when applicable
3. Ensure cultural references are accurately conveyed
4. Output valid JSON only (no markdown, no preamble)

{context_section}Text to translate:
{text}

Respond with JSON matching this schema:
{{
    "source_text": "original text",
    "draft_translation": "your translation",
    "confidence": 0.95,
    "terminology_notes": "any key translation decisions",
    "model_name": "claude-3-5-sonnet-20241022"
}}"""
        
        return prompt
    
    def get_output_schema(self) -> Type[BaseModel]:
        return TranslatorAgentOutput


# ============================================================================
# STYLIST AGENT
# ============================================================================

class StylistAgent(BaseAgent):
    """
    Applies historical-diplomatic style to translated text.
    Focus: Tone, formality, archaic expressions, diplomatic language.
    """
    
    def __init__(
        self,
        provider: AgentProvider = AgentProvider.ANTHROPIC,
        style_guide: Optional[str] = None,
    ):
        super().__init__(
            name="stylist",
            provider=provider,
            max_retries=3,
            timeout_seconds=30
        )
        self.style_guide = style_guide or "historical-diplomatic"
    
    async def process(self, input_data: str, **kwargs) -> str:
        """
        Apply historical-diplomatic style to translation.
        
        Args:
            input_data: Draft translation to stylize
            original_text: Original text for reference
            context: Historical or diplomatic context
        """
        original_text = kwargs.get("original_text", "")
        context = kwargs.get("context", "")
        
        prompt = self._build_prompt(
            input_data,
            original_text,
            context
        )
        
        response = await self.call_llm(
            prompt,
            output_schema=StylistAgentOutput
        )
        
        return response
    
    def _build_prompt(
        self,
        draft_translation: str,
        original_text: str = "",
        context: str = "",
    ) -> str:
        """Construct stylist prompt"""
        
        original_section = f"Original text: {original_text}\n\n" if original_text else ""
        context_section = f"Historical context: {context}\n\n" if context else ""
        
        prompt = f"""You are an expert in historical and diplomatic language styling.

Your task is to transform the given translation into formal, historical-diplomatic style.

STYLE GUIDELINES:
- Use elevated, formal register (avoid colloquialisms)
- Incorporate archaic but understandable vocabulary where appropriate
- Use diplomatic phrasing for sensitive topics
- Maintain clarity while adding gravitas
- Preserve all meaning from the original translation

{original_section}{context_section}Draft translation to stylize:
{draft_translation}

Respond with JSON matching this schema:
{{
    "draft_translation": "{draft_translation}",
    "styled_translation": "your stylized version",
    "style_notes": "explanation of changes",
    "tone_indicators": ["formal", "archaic", "diplomatic"],
    "model_name": "claude-3-5-sonnet-20241022"
}}

Important: Output ONLY valid JSON, no other text."""
        
        return prompt
    
    def get_output_schema(self) -> Type[BaseModel]:
        return StylistAgentOutput


# ============================================================================
# QUALITY CONTROL AGENT
# ============================================================================

class QualityControlAgent(BaseAgent):
    """
    Reviews translation and applies corrections via structured output.
    Focus: Accuracy, style consistency, grammar, terminology verification.
    """
    
    def __init__(
        self,
        provider: AgentProvider = AgentProvider.ANTHROPIC,
        min_quality_score: int = 75,
    ):
        super().__init__(
            name="qa",
            provider=provider,
            max_retries=2,
            timeout_seconds=60  # QA is more thorough
        )
        self.min_quality_score = min_quality_score
    
    async def process(self, input_data: str, **kwargs) -> str:
        """
        Review and correct translation.
        
        Args:
            input_data: Styled translation to review
            original_text: Original for reference
            draft_translation: Draft for reference
            context: Any additional context
        """
        original_text = kwargs.get("original_text", "")
        draft_translation = kwargs.get("draft_translation", "")
        context = kwargs.get("context", "")
        
        prompt = self._build_prompt(
            input_data,
            original_text,
            draft_translation,
            context
        )
        
        response = await self.call_llm(
            prompt,
            output_schema=QualityControlResult
        )
        
        return response
    
    def _build_prompt(
        self,
        styled_translation: str,
        original_text: str = "",
        draft_translation: str = "",
        context: str = "",
    ) -> str:
        """Construct QA prompt"""
        
        original_section = f"Original text: {original_text}\n" if original_text else ""
        draft_section = f"Draft translation: {draft_translation}\n" if draft_translation else ""
        context_section = f"Context: {context}\n\n" if context else ""
        
        prompt = f"""You are a professional translator and quality assurance expert.

Review the following stylized translation for accuracy, style consistency, and quality.

{original_section}{draft_section}{context_section}Styled translation to review:
{styled_translation}

REVIEW CHECKLIST:
1. Accuracy: Does it accurately convey the original meaning?
2. Terminology: Are technical/proper terms used correctly?
3. Grammar: Are there any grammatical errors?
4. Tone: Is the historical-diplomatic tone consistent?
5. Context: Does it make sense in historical context?
6. Cultural: Are cultural references appropriate?

Respond with JSON containing:
- score (0-100): Overall quality
- approved (bool): Ready for publication?
- issues: List of issues found with type, location, description, severity (1-5)
- final_text: Your corrected version (or same if no corrections)
- recommendations: General improvement notes

Example JSON structure:
{{
    "score": 85,
    "approved": true,
    "issues": [
        {{
            "issue_type": "terminology",
            "location": "phrase containing 'example'",
            "description": "Better term would be X",
            "suggestion": "suggested replacement",
            "severity": 2
        }}
    ],
    "final_text": "complete corrected translation",
    "recommendations": "Consider X for future translations"
}}

Output ONLY valid JSON, no other text."""
        
        return prompt
    
    def get_output_schema(self) -> Type[BaseModel]:
        return QualityControlResult


# ============================================================================
# BATCH VALIDATION AGENT (Optional helper)
# ============================================================================

class ValidationHelperAgent(BaseAgent):
    """
    Helper agent for validating outputs from other agents.
    Used when parsing or validation fails.
    """
    
    async def process(self, input_data: str, **kwargs) -> str:
        """Validate and attempt to fix malformed JSON"""
        
        prompt = f"""You are a JSON validator and fixer.

The following text should be valid JSON but may have formatting issues.
Fix any issues and return ONLY the corrected JSON.

Invalid JSON:
{input_data}

Output: (corrected JSON only)"""
        
        response = await self.call_llm(prompt)
        return response
    
    def get_output_schema(self) -> Type[BaseModel]:
        # This agent returns raw JSON, no schema validation
        return None


# ============================================================================
# Factory for creating agents with shared configuration
# ============================================================================

class AgentFactory:
    """Factory for creating agent instances with consistent configuration"""
    
    @staticmethod
    def create_translator(
        provider: AgentProvider = AgentProvider.ANTHROPIC,
    ) -> TranslatorAgent:
        return TranslatorAgent(provider=provider)
    
    @staticmethod
    def create_stylist(
        provider: AgentProvider = AgentProvider.ANTHROPIC,
    ) -> StylistAgent:
        return StylistAgent(provider=provider)
    
    @staticmethod
    def create_qa(
        provider: AgentProvider = AgentProvider.ANTHROPIC,
        min_quality_score: int = 75,
    ) -> QualityControlAgent:
        return QualityControlAgent(
            provider=provider,
            min_quality_score=min_quality_score
        )
    
    @staticmethod
    def create_validator() -> ValidationHelperAgent:
        return ValidationHelperAgent(
            name="validator",
            provider=AgentProvider.ANTHROPIC
        )
