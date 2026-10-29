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
import asyncio
import warnings
import logging

# Suppress internal SDK noise and warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")
warnings.filterwarnings("ignore", category=ResourceWarning)
logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.events.event_actions import EventActions
from google.adk.events import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import START, JoinNode, Workflow, node
from google.genai import types

MODEL = "gemini-3.8-flash"

# ===== Section 1: Parallel Data Fetchers =====
async def fetch_profile(node_input):
    await asyncio.sleep(0.3)
    return {"name": "Alice", "tier": "Gold", "account_age": "2 years"}

async def fetch_orders(node_input):
    await asyncio.sleep(0.3)
    return {"recent_orders": 3, "last_order": "Pro Laptop #8492"}

async def fetch_billing(node_input):
    await asyncio.sleep(0.3)
    return {"outstanding_balance": 0, "payment_method": "Visa-4242"}

# ===== Section 2: Classifier / Router =====
def classify_and_route(node_input, ctx):
    """Inspects user message in state and routes to the right specialist."""
    if ctx.user_content and ctx.user_content.parts:
        user_text = "".join(p.text for p in ctx.user_content.parts if p.text).lower()
    elif "user_message" in ctx.state:
        user_text = str(ctx.state["user_message"]).lower()
    print(f"user_text : ${user_text}")
    profile = node_input.get("fetch_profile", {})
    print(f"profile : ${profile}")
    context_summary = f"Customer: {profile.get('name', 'User')}, Tier: {profile.get('tier', 'Standard')}"
    print(f"context_summary : ${context_summary}")
    
    if "approval_status" in ctx.state or "refund" in user_text or "charge" in user_text or "bill" in user_text:
        route = "billing"
    elif "crash" in user_text or "error" in user_text or "bug" in user_text:
        route = "tech"
    elif "track" in user_text or "package" in user_text or "delivery" in user_text:
        route = "shipping"
    else:
        route = "general"
        
    return Event(output=context_summary, actions=EventActions(route=route))

# ===== Section 3: Dynamic Tech Troubleshooting Node =====
diagnose_agent = Agent(
    name="tech_diagnostician",
    model=MODEL,
    instruction="Suggest ONE specific troubleshooting step in 1 sentence.",
)

@node(rerun_on_resume=True)
async def dynamic_troubleshoot(ctx):
    """Loops up to 2 attempts using ctx.run_node before escalating."""
    for attempt in (1, 2):
        print(f"  [Troubleshoot Loop] Attempt {attempt}...")
        result = await ctx.run_node(diagnose_agent)
        print(f"  [Diagnostician {attempt}]: {result}")
    return "Troubleshooting attempts completed. Escalated to Tier 2."

# ===== Section 4: Billing Agent & HITL Gate =====
billing_agent = Agent(
    name="billing_specialist",
    model=MODEL,
    instruction="Acknowledge the billing refund inquiry empathetically in 1 sentence.",
)

def check_refund_hitl(node_input, ctx):
    """HITL Gate: If refund amount > $100, pause for human approval."""
    already_approved = ctx.state.get("approval_status", None)
    if already_approved == "approved":
        return Event(output="Refund Processed: APPROVED by Manager", actions=EventActions(route="approved"))
    elif already_approved == "rejected":
        return Event(output="Refund Processed: REJECTED by Manager", actions=EventActions(route="rejected"))

    refund_amount = ctx.state.get("refund_amount", 150)
    ctx.state["pending_refund"] = refund_amount
    ctx.state["needs_approval"] = True
    print(f"  [HITL Gate] Refund of ${refund_amount} exceeds $100 auto-limit. Pausing for approval.")
    return Event(output=f"PAUSED: Requires manager approval for ${refund_amount} refund")

def process_approved(node_input):
    return f"Final Status: {node_input}"

# ===== Section 5: Shipping & General Agents =====
shipping_agent = Agent(
    name="shipping_specialist",
    model=MODEL,
    instruction="Provide a tracking status update for Order #8492 in 1 sentence.",
)

general_agent = Agent(
    name="general_specialist",
    model=MODEL,
    instruction="Answer general support inquiry helpfully in 1 sentence.",
)

# ===== Section 6: Build Unified Graph =====
join = JoinNode(name="data_joiner")

root_agent = Workflow(
    name="complete_support_system",
    edges=[
        # 1. Parallel Fan-out from START to data fetchers
        (START, fetch_profile, join),
        (START, fetch_orders, join),
        (START, fetch_billing, join),
        
        # 2. Join -> Classify & Route
        (join, classify_and_route),
        
        # 3. Conditional branches
        (classify_and_route, {
            "tech": dynamic_troubleshoot,
            "billing": billing_agent,
            "shipping": shipping_agent,
            "general": general_agent,
        }),
        
        # 4. Billing flows into HITL Gate
        (billing_agent, check_refund_hitl),
        (check_refund_hitl, {
            "approved": process_approved,
        }),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

