"""Gemini OCR module for extracting text from images using Google's Gemini model."""

import os
from typing import Any

from PIL import Image
from autogen_agentchat.messages import MultiModalMessage
from autogen_agentchat.agents import AssistantAgent
from autogen_core import Image as AGImage
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Constants
DEFAULT_MODEL_NAME: str = 'gemini-2.0-flash'
SYSTEM_MESSAGE: str = "You are a helpful assistant that can extract text from images."


class GeminiOCRError(Exception):
    """Base exception for Gemini OCR operations."""
    pass


class ImageProcessingError(GeminiOCRError):
    """Raised when image processing fails."""
    pass


class ModelError(GeminiOCRError):
    """Raised when model operations fail."""
    pass


class GeminiOCR:
    """OCR client using Google's Gemini model for text extraction from images.

    This class provides functionality to extract text from images using
    Google's Gemini model through the AutoGen framework.

    Attributes:
        model_name: The name of the Gemini model to use.
        client: The OpenAI chat completion client.
        agent: The assistant agent for processing requests.
    """

    def __init__(self, api_key: str,  model_name: str = DEFAULT_MODEL_NAME, output_content_type: Any = None) -> None:
        """Initialize the Gemini OCR client.

        Args:
            api_key: Google API key for authentication.
            model_name: Name of the Gemini model to use. Defaults to 'gemini-2.0-flash'.

        Raises:
            ModelError: If client initialization fails.
        """
        if not api_key:
            raise ModelError("API key cannot be empty")

        self.model_name = model_name

        try:
            self.client = OpenAIChatCompletionClient(
                model=model_name,
                api_key=api_key
            )

            self.agent = AssistantAgent(
                name="gemini_ocr",
                model_client=self.client,
                system_message=SYSTEM_MESSAGE,
                output_content_type=output_content_type
            )
        except Exception as e:
            raise ModelError(f"Failed to initialize Gemini OCR client: {e}")

    async def ocr(self, message: str, image_path: str) -> str:
        """Extract text from an image using the specified prompt.

        Args:
            message: The prompt message describing what to extract from the image.
            image_path: Path to the image file to process.

        Returns:
            Extracted text content from the image.

        Raises:
            ImageProcessingError: If image processing fails.
            ModelError: If model inference fails.
        """
        if not message:
            raise ImageProcessingError("Message cannot be empty")

        if not os.path.exists(image_path):
            raise ImageProcessingError(f"Image file not found: {image_path}")

        try:
            # Load and validate image
            image = self._load_image(image_path)

            # Create multimodal message
            multi_modal_message = self._create_multimodal_message(
                message, image)

            # Process with agent
            result = await self._process_with_agent(multi_modal_message)

            return self._extract_content(result)

        except Exception as e:
            if isinstance(e, (ImageProcessingError, ModelError)):
                raise
            raise ModelError(f"OCR processing failed: {e}")

    def _load_image(self, image_path: str) -> Image.Image:
        """Load and validate an image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Loaded PIL Image object.

        Raises:
            ImageProcessingError: If image loading fails.
        """
        try:
            image = Image.open(image_path)
            # Validate image can be read
            image.verify()
            # Reopen for actual use (verify() closes the file)
            return Image.open(image_path)
        except Exception as e:
            raise ImageProcessingError(
                f"Failed to load image {image_path}: {e}")

    def _create_multimodal_message(self, message: str, image: Image.Image) -> MultiModalMessage:
        """Create a multimodal message with text and image content.

        Args:
            message: Text message content.
            image: PIL Image object.

        Returns:
            MultiModalMessage object ready for processing.
        """
        return MultiModalMessage(
            content=[
                message,
                AGImage(image)
            ],
            source="user"
        )

    async def _process_with_agent(self, message: MultiModalMessage) -> object:
        """Process the multimodal message with the agent.

        Args:
            message: MultiModalMessage to process.

        Returns:
            Agent processing result.

        Raises:
            ModelError: If agent processing fails.
        """
        try:
            return await self.agent.run(task=message)
        except Exception as e:
            raise ModelError(f"Agent processing failed: {e}")

    def _extract_content(self, result: object) -> str:
        """Extract text content from agent result.

        Args:
            result: Agent processing result.

        Returns:
            Extracted text content.

        Raises:
            ModelError: If content extraction fails.
        """
        try:
            if hasattr(result, 'messages') and result.messages:
                return result.messages[-1].content
            else:
                raise ModelError("No messages found in agent result")
        except Exception as e:
            raise ModelError(f"Failed to extract content from result: {e}")
