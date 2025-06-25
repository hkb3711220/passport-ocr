"""Unit tests for RetryHandler class."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
import pytest

from main import RetryHandler

pytestmark = pytest.mark.unit


class TestRetryHandler:
    """Test cases for RetryHandler class."""

    def test_init(self, app_config, test_logger):
        """Test RetryHandler initialization."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        assert handler.config == app_config
        assert handler.logger == test_logger

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self, app_config, test_logger):
        """Test successful operation on first attempt."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        mock_func = AsyncMock(return_value="success")
        
        result = await handler.retry_with_backoff(
            mock_func, 
            "arg1", 
            operation_name="test_operation",
            kwarg1="value1"
        )
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, app_config, test_logger):
        """Test successful operation after initial failures."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        # Mock function that fails twice then succeeds
        mock_func = AsyncMock()
        mock_func.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            "success"
        ]
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await handler.retry_with_backoff(
                mock_func,
                operation_name="test_operation"
            )
        
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2  # Two retries before success

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, app_config, test_logger):
        """Test when all retry attempts are exhausted."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Persistent failure")
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(Exception, match="Persistent failure"):
                await handler.retry_with_backoff(
                    mock_func,
                    operation_name="test_operation"
                )
        
        # Should try max_retries + 1 times (initial + retries)
        assert mock_func.call_count == app_config.max_retries + 1
        assert mock_sleep.call_count == app_config.max_retries

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, app_config, test_logger):
        """Test that delays follow exponential backoff pattern."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Always fails")
        
        sleep_delays = []
        
        async def capture_sleep(delay):
            sleep_delays.append(delay)
        
        with patch('asyncio.sleep', side_effect=capture_sleep):
            with pytest.raises(Exception):
                await handler.retry_with_backoff(
                    mock_func,
                    operation_name="test_operation"
                )
        
        # Check that delays increase exponentially (with jitter)
        assert len(sleep_delays) == app_config.max_retries
        
        # Base delays should be approximately: 0.1, 0.2 (with jitter)
        base_delay_1 = app_config.retry_delay * (app_config.retry_backoff_factor ** 0)
        base_delay_2 = app_config.retry_delay * (app_config.retry_backoff_factor ** 1)
        
        # Account for jitter (10-30% of delay)
        assert sleep_delays[0] >= base_delay_1 * 1.1  # At least base + min jitter
        assert sleep_delays[0] <= base_delay_1 * 1.3  # At most base + max jitter
        
        assert sleep_delays[1] >= base_delay_2 * 1.1
        assert sleep_delays[1] <= base_delay_2 * 1.3
        
        # Second delay should be larger than first
        assert sleep_delays[1] > sleep_delays[0]

    @pytest.mark.asyncio
    async def test_max_retry_delay_cap(self, app_config, test_logger):
        """Test that retry delay is capped at max_retry_delay."""
        # Set a very small max_retry_delay to test the cap
        app_config.max_retry_delay = 0.2
        app_config.retry_delay = 0.1
        app_config.retry_backoff_factor = 10.0  # Large multiplier
        
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Always fails")
        
        sleep_delays = []
        
        async def capture_sleep(delay):
            sleep_delays.append(delay)
        
        with patch('asyncio.sleep', side_effect=capture_sleep):
            with pytest.raises(Exception):
                await handler.retry_with_backoff(
                    mock_func,
                    operation_name="test_operation"
                )
        
        # All delays should be capped at max_retry_delay + jitter
        for delay in sleep_delays:
            assert delay <= app_config.max_retry_delay * 1.3  # Max delay + max jitter

    @pytest.mark.asyncio
    async def test_jitter_randomization(self, app_config, test_logger):
        """Test that jitter adds randomization to delays."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Always fails")
        
        all_delays = []
        
        # Run multiple times to collect delay variations
        for _ in range(5):
            sleep_delays = []
            
            async def capture_sleep(delay):
                sleep_delays.append(delay)
            
            with patch('asyncio.sleep', side_effect=capture_sleep):
                with pytest.raises(Exception):
                    await handler.retry_with_backoff(
                        mock_func,
                        operation_name="test_operation"
                    )
            
            all_delays.extend(sleep_delays)
        
        # Should have some variation in delays due to jitter
        unique_delays = set(all_delays)
        assert len(unique_delays) > 1, "Jitter should create variation in delays"

    @pytest.mark.asyncio
    async def test_logging_messages(self, app_config):
        """Test that appropriate log messages are generated."""
        mock_logger = Mock()
        handler = RetryHandler(config=app_config, logger=mock_logger)
        
        mock_func = AsyncMock()
        mock_func.side_effect = [Exception("First failure"), "success"]
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await handler.retry_with_backoff(
                mock_func,
                operation_name="test_operation"
            )
        
        assert result == "success"
        
        # Check that logger was called with appropriate messages
        assert mock_logger.info.call_count >= 1
        assert mock_logger.warning.call_count >= 1

    @pytest.mark.asyncio
    async def test_different_exception_types(self, app_config, test_logger):
        """Test handling of different exception types."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        # Test with different exception types
        exceptions = [
            ValueError("Value error"),
            ConnectionError("Connection error"),
            TimeoutError("Timeout error")
        ]
        
        for exception in exceptions:
            mock_func = AsyncMock()
            mock_func.side_effect = exception
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(type(exception)):
                    await handler.retry_with_backoff(
                        mock_func,
                        operation_name="test_operation"
                    )

    @pytest.mark.asyncio
    async def test_function_with_return_value(self, app_config, test_logger):
        """Test that function return values are properly passed through."""
        handler = RetryHandler(config=app_config, logger=test_logger)
        
        expected_result = {"data": "complex_object", "count": 42}
        mock_func = AsyncMock(return_value=expected_result)
        
        result = await handler.retry_with_backoff(
            mock_func,
            operation_name="test_operation"
        )
        
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_zero_retries_config(self, test_logger):
        """Test behavior when max_retries is set to 0."""
        from main import AppConfig
        
        config = AppConfig(
            folder_id="test",
            api_key="test",
            max_retries=0  # No retries
        )
        
        handler = RetryHandler(config=config, logger=test_logger)
        
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Immediate failure")
        
        with pytest.raises(Exception, match="Immediate failure"):
            await handler.retry_with_backoff(
                mock_func,
                operation_name="test_operation"
            )
        
        # Should only be called once (no retries)
        assert mock_func.call_count == 1