# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

MODEL = "gemini-3.8-flash"

# 데모용 인메모리 주문 데이터베이스 (고정된 정답 -> 평가 시 Reference-based 채점용)
MOCK_ORDERS = {
    "ORD-1001": {
        "customer": "Alice",
        "item": "Pro Laptop 16-inch",
        "status": "In Transit",
        "estimated_delivery": "2026-11-02",
        "carrier": "FedEx",
        "amount": "$1,800",
    },
    "ORD-1002": {
        "customer": "Bob",
        "item": "Wireless Noise-Canceling Headphones",
        "status": "Delivered",
        "delivered_at": "2026-10-25",
        "carrier": "UPS",
        "amount": "$350",
    },
}

# 카테고리별 환불 규정 데이터 (고정된 정답 -> 평가 시 Reference-based 채점용)
REFUND_POLICIES = {
    "electronics": "Electronics can be returned within 30 days of delivery in original packaging. A 10% restocking fee applies if opened.",
    "apparel": "Apparel and clothing items can be returned within 60 days for a full refund, provided tags are still attached.",
    "digital": "Digital downloads and software licenses are non-refundable once the activation key has been revealed.",
}


def get_order_status(order_id: str) -> dict:
    """Looks up the shipping and delivery status of a customer order.

    Args:
        order_id: The order ID string (e.g., 'ORD-1001', 'ORD-1002').

    Returns:
        A dictionary containing order details and current shipping status.
    """
    normalized_id = order_id.strip().upper()
    if normalized_id in MOCK_ORDERS:
        return {"order_id": normalized_id, **MOCK_ORDERS[normalized_id]}
    return {
        "order_id": normalized_id,
        "error": f"Order '{normalized_id}' not found. Valid sample order IDs are ORD-1001 and ORD-1002.",
    }


def get_refund_policy(category: str) -> str:
    """Retrieves the company refund and return policy for a product category.

    Args:
        category: Product category ('electronics', 'apparel', or 'digital').

    Returns:
        The official refund policy description for the given category.
    """
    key = category.strip().lower()
    for policy_key, policy_text in REFUND_POLICIES.items():
        if policy_key in key:
            return policy_text
    return (
        "Standard policy: Most physical items can be returned within 30 days of delivery. "
        "Please specify 'electronics', 'apparel', or 'digital' for exact category rules."
    )


def create_support_ticket(customer_name: str, issue_summary: str) -> dict:
    """Creates a customer support ticket for issues requiring human follow-up or refund approval.

    Args:
        customer_name: The name of the customer requesting support.
        issue_summary: A brief description of the problem or request.

    Returns:
        A dictionary with the generated ticket ID, timestamp, and status.
    """
    now_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    ticket_id = f"TKT-{now_kst.strftime('%H%M%S')}"
    return {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_summary": issue_summary,
        "status": "OPEN (Assigned to Tier-2 Support)",
        "created_at": now_kst.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


SYSTEM_INSTRUCTION = """You are a helpful and empathetic Customer Support Agent for an online store.
Follow these guidelines strictly:
1. When a user asks about an order status or delivery tracking, always call `get_order_status`.
2. When a user asks about return or refund rules, always call `get_refund_policy`.
3. When a user wants to file a complaint, request a human agent, or open a support ticket, call `create_support_ticket`.
4. Always provide clear, polite, and accurate answers grounded only in the tool outputs.
"""

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=SYSTEM_INSTRUCTION,
    tools=[get_order_status, get_refund_policy, create_support_ticket],
)

app = App(
    root_agent=root_agent,
    name="app",
)
