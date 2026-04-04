"""Kafka component implementing the Component lifecycle protocol."""

from __future__ import annotations

from pykit_component import Health, HealthStatus
from pykit_messaging.kafka.config import KafkaConfig
from pykit_messaging.kafka.consumer import KafkaConsumer
from pykit_messaging.kafka.producer import KafkaProducer


class KafkaComponent:
    """Lifecycle-managed Kafka component wrapping a producer and consumer."""

    def __init__(self, config: KafkaConfig) -> None:
        self._config = config
        self._producer = KafkaProducer(config)
        self._consumer = KafkaConsumer(config)
        self._started = False

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def producer(self) -> KafkaProducer:
        return self._producer

    @property
    def consumer(self) -> KafkaConsumer:
        return self._consumer

    async def start(self) -> None:
        """Start the producer and consumer."""
        await self._producer.start()
        await self._consumer.start()
        self._started = True

    async def stop(self) -> None:
        """Stop the consumer and producer (reverse order)."""
        self._started = False
        await self._consumer.stop()
        await self._producer.stop()

    async def health(self) -> Health:
        """Return current health status."""
        if not self._started:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="not started")
        return Health(name=self.name, status=HealthStatus.HEALTHY)
