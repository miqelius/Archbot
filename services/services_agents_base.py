"""
services/agents/base.py - Abstract base class for LLM agents
Defines interface, error handling, and shared utilities
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar
from dataclasses import dataclass, field
from datetime import datetime
import logging
import httpx
from enum import Enum

from pydantic import BaseModel, ValidationError
from core.core_config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


@dataclass
class AgentMetrics:
    """Metrics collected during agent execution"""
    
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    input_tokens: int = 0
    output_tokens: int = 0
    model_name: str = ""
    error: Optional[str] = None
    retry_count: int = 0
    
    @property
    def duration_seconds(self) -> float:
        """Calculate execution duration"""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used"""
        return self.input_tokens + self.output_tokens
    
    def to_dict(self) -> dict:
        """Export as dictionary for logging"""
        return {
            "duration_seconds": self.duration_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "model_name": self.model_name,
            "retry_count": self.retry_count,
            "error": self.error,
        }


class AgentException(Exception):
    """Base exception for agent errors"""
    
    def __init__(self, message: str, metrics: Optional[AgentMetrics] = None):
        self.message = message
        self.metrics = metrics
        super().__init__(message)


class RateLimitException(AgentException):
    """Rate limit error from LLM API"""
    pass


class ValidationException(AgentException):
    """Output validation error"""
    pass


class TimeoutException(AgentException):
    """Request timeout"""
    pass


class BaseAgent(ABC):
    """
    Abstract base class for all LLM agents.
    Handles common concerns: retries, logging, metrics, type validation.
    """
    
    def __init__(
        self,
        name: str,
        provider: AgentProvider = AgentProvider.ANTHROPIC,
        max_retries: int = 3,
        timeout_seconds: int = 30,
    ):
        """
        Initialize agent.
        
        Args:
            name: Agent identifier (e.g., "translator", "stylist", "qa")
            provider: LLM provider to use
            max_retries: Maximum retry attempts on transient errors
            timeout_seconds: HTTP request timeout
        """
        self.name = name
        self.provider = provider
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.metrics: Optional[AgentMetrics] = None
        self.logger = logging.getLogger(f"Agent.{name}")
    
    @abstractmethod
    async def process(self, input_data: str, **kwargs) -> str:
        """
        Process input through the agent.
        
        Args:
            input_data: Text or serialized data to process
            **kwargs: Additional agent-specific parameters
        
        Returns:
            Raw response from LLM (before structured validation)
        """
        pass
    
    @abstractmethod
    def get_output_schema(self) -> Type[T]:
        """
        Return Pydantic schema for structured output validation.
        
        Override this to enable function calling / structured output.
        """
        pass
    
    async def execute(
        self,
        input_data: str,
        output_type: Optional[Type[T]] = None,
        **kwargs
    ) -> tuple[Any, AgentMetrics]:
        """
        Execute agent with retry logic, metrics, and output validation.
        
        Args:
            input_data: Input text
            output_type: Pydantic model for output validation (if using structured output)
            **kwargs: Additional parameters for process()
        
        Returns:
            (validated_output, metrics)
        
        Raises:
            AgentException: On persistent failures
        """
        self.metrics = AgentMetrics(model_name=self.name)
        
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.info(f"Executing {self.name} (attempt {attempt + 1}/{self.max_retries + 1})")
                
                # Call the actual agent implementation
                raw_response = await self.process(input_data, **kwargs)
                
                # Validate output if schema provided
                if output_type:
                    try:
                        validated_output = output_type.model_validate_json(raw_response)
                        self.logger.info(f"{self.name} executed successfully")
                        self.metrics.end_time = datetime.utcnow()
                        return validated_output, self.metrics
                    except ValidationError as e:
                        self.logger.error(f"Output validation failed: {e}")
                        raise ValidationException(
                            f"{self.name} output validation failed: {str(e)}",
                            self.metrics
                        )
                else:
                    # Return raw response if no schema
                    self.metrics.end_time = datetime.utcnow()
                    return raw_response, self.metrics
            
            except RateLimitException as e:
                # Rate limit - exponential backoff
                if attempt < self.max_retries:
                    wait_seconds = 2 ** attempt
                    self.logger.warning(
                        f"{self.name} rate limited, retrying in {wait_seconds}s"
                    )
                    self.metrics.retry_count += 1
                    await asyncio.sleep(wait_seconds)
                else:
                    self.metrics.end_time = datetime.utcnow()
                    raise
            
            except TimeoutException as e:
                # Timeout - retry immediately
                if attempt < self.max_retries:
                    self.logger.warning(f"{self.name} timed out, retrying")
                    self.metrics.retry_count += 1
                else:
                    self.metrics.end_time = datetime.utcnow()
                    raise
            
            except Exception as e:
                # Unexpected error
                self.metrics.error = str(e)
                self.metrics.end_time = datetime.utcnow()
                self.logger.error(f"{self.name} failed: {e}", exc_info=True)
                raise AgentException(
                    f"{self.name} execution failed: {str(e)}",
                    self.metrics
                )
        
        # Should not reach here
        raise AgentException(f"{self.name} exhausted retries", self.metrics)
    
    async def call_llm(
        self,
        prompt: str,
        output_schema: Optional[Type[T]] = None,
    ) -> str:
        """
        Make API call to LLM provider.
        
        Args:
            prompt: Full prompt for LLM
            output_schema: Pydantic model for structured output (function calling)
        
        Returns:
            Raw JSON response from LLM
        
        Raises:
            RateLimitException, TimeoutException, ValidationException
        """
        if self.provider == AgentProvider.ANTHROPIC:
            return await self._call_anthropic(prompt, output_schema)
        elif self.provider == AgentProvider.OPENAI:
            return await self._call_openai(prompt, output_schema)
        elif self.provider == AgentProvider.GOOGLE:
            return await self._call_google(prompt, output_schema)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _call_anthropic(
        self,
        prompt: str,
        output_schema: Optional[Type[T]] = None,
    ) -> str:
        """Call Anthropic Claude API with optional structured output"""
        import json
        from anthropic import AsyncAnthropic, APIRateLimitError, APITimeoutError
        
        client = AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
        
        try:
            # Build request
            request_kwargs = {
                "model": settings.llm.anthropic_model,
                "max_tokens": settings.llm.max_tokens,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
            
            # Add structured output if schema provided
            if output_schema:
                request_kwargs["tools"] = [
                    {
                        "name": "return_structured_output",
                        "description": "Return structured output matching the schema",
                        "input_schema": output_schema.model_json_schema(),
                    }
                ]
                request_kwargs["tool_choice"] = {
                    "type": "tool",
                    "name": "return_structured_output"
                }
            
            response = await client.messages.create(**request_kwargs)
            
            # Extract content
            if output_schema and response.content[0].type == "tool_use":
                # Structured output via tool_use
                result_json = json.dumps(response.content[0].input)
            else:
                # Plain text response
                result_json = response.content[0].text
            
            # Track tokens
            self.metrics.input_tokens = response.usage.input_tokens
            self.metrics.output_tokens = response.usage.output_tokens
            
            return result_json
        
        except APIRateLimitError as e:
            raise RateLimitException(f"Claude API rate limit: {str(e)}", self.metrics)
        except APITimeoutError as e:
            raise TimeoutException(f"Claude API timeout: {str(e)}", self.metrics)
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            raise AgentException(f"Claude API error: {str(e)}", self.metrics)
    
    async def _call_openai(
        self,
        prompt: str,
        output_schema: Optional[Type[T]] = None,
    ) -> str:
        """Call OpenAI GPT API with optional structured output"""
        # Placeholder - implement similarly to _call_anthropic
        raise NotImplementedError("OpenAI provider not yet implemented")
    
    async def _call_google(
        self,
        prompt: str,
        output_schema: Optional[Type[T]] = None,
    ) -> str:
        """Call Google Gemini API with optional structured output"""
        # Placeholder - implement similarly to _call_anthropic
        raise NotImplementedError("Google provider not yet implemented")


import asyncio
