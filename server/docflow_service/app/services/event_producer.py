import json
from aiokafka import AIOKafkaProducer
import asyncio
import os
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
TOPIC = os.getenv("KAFKA_TOPIC_USER_EVENTS")

producer = None

async def get_producer():
    global producer
    if producer is None:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await producer.start()
    return producer

async def send_event(event_type: str, document: dict):
    producer = await get_producer()
    event = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": document_data
    }
    await producer.send(KAFKA_TOPIC_USER_EVENTS, value=event)