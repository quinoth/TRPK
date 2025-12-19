from aiokafka import AIOKafkaProducer
import json
import asyncio
import os

# Получаем из .env
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_USER_EVENTS = "user_events"

producer = None

async def get_kafka_producer():
    """Глобальный producer"""
    global producer
    if not producer:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await producer.start()
    return producer

async def send_event(topic: str, message: dict):
    
    try:
        prod = await get_kafka_producer()
        await prod.send_and_wait(topic, message)
        print(f" Событие отправлено в {topic}: {message}")
    except Exception as e:
        print(f" Ошибка отправки в Kafka: {e}")

async def close_kafka_producer():
    
    if producer:
        await producer.stop()