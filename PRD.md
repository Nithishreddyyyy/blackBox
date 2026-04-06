# Product Requirements Document (PRD)

**Product:** AI Red‑Team Challenge Platform
**Version:** 1.0
**Status:** MVP Specification
**Last Updated:** 2026

---

# 1. Product Overview

## 1.1 Summary

The AI Red‑Team Challenge Platform is a web-based competition system where participants interact with a controlled Large Language Model (LLM) and attempt to achieve a predefined objective (for example, reaching a specific output or bypassing model constraints).

Participants use a chat interface to prompt the model while administrators monitor activity in real time through an admin dashboard.

The platform provides:

• Separate login systems for **Admins and Users**
• A **chat interface** for participants
• A **live monitoring dashboard** for admins
• Full **prompt logging and analytics**
• Admin‑controlled **message limits and rules**
• **Leaderboard and winner determination**
• Ability for admins to broadcast **global notifications** (ex: "Round 1 Start", "Round 2", "5 Minutes Remaining") to all users

The system is designed to support **approximately 20 concurrent participants** during a live event.

---

# 2. Problem Statement

During AI competitions or security challenges, organizers need a controlled environment where participants interact with AI models while administrators monitor progress and enforce rules.

Without a proper platform:

• Prompt usage cannot be tracked reliably
• Competition rules cannot be enforced automatically
• Determining winners becomes subjective
• Admins cannot monitor participants in real time

This system solves these issues by providing **structured logging, monitoring, and control over AI interaction sessions.**

---

# 3. Goals

## 3.1 Primary Goals

1. Provide **secure login systems** for admins and users.
2. Enable participants to **interact with an LLM through chat**.
3. Track **all prompts, responses, timestamps, and usage statistics**.
4. Provide a **real‑time admin dashboard**.
5. Allow admins to **control rules during the competition**.
6. Determine winners using **objective scoring metrics**.

## 3.2 Secondary Goals

• Allow switching between **local LLM and API-based LLM providers**.
• Maintain system responsiveness with **~20 concurrent users**.
• Keep the UI simple and optimized for live events.

---

# 4. Non‑Goals

The following are intentionally **out of scope for Version 1.0**:

• Mobile applications
• Public social feed
• Complex permission hierarchies beyond Admin/User
• Billing or payment systems
• Multi‑tenant SaaS deployment

---

# 5. Target Users

## 5.1 Admins

Event organizers responsible for controlling the competition.

Admins must be able to:

• Monitor participant progress
• View prompt usage statistics
• Change competition rules
• Send global notifications
• Determine winners

## 5.2 Participants

Registered users competing in the challenge.

Participants must be able to:

• Log in
• Read challenge instructions
• Chat with the AI model
• Track their remaining attempts

---

# 6. Technology Stack

## 6.1 Frontend

Framework: **Next.js**
Styling: **TailwindCSS**
Optional UI library: **shadcn/ui**

Responsibilities:

• Authentication UI
• User chat interface
• Admin dashboard
• Leaderboard view
• Notification display

## 6.2 Backend

Framework: **FastAPI**

Responsibilities:

• Authentication
• Session management
• Prompt routing
• LLM provider abstraction
• Rate limiting
• Logging
• Admin APIs

## 6.3 Database

**Recommended Database: MySQL**

Reasons:

• Structured relational data
• Easy analytics and reporting
• Strong integrity constraints
• Efficient leaderboard queries

MongoDB could work, but relational structure fits this system better.

## 6.4 LLM Provider Layer

The backend must include an **LLM abstraction layer**.

Possible providers:

• Local: **Ollama**
• API: **OpenRouter**
• API: **OpenAI**

This allows switching models using environment variables without changing core code.

---

# 7. High Level System Architecture

System flow:

Next.js Frontend
↓
FastAPI Backend
↓
LLM Provider Layer
↓
LLM (Ollama or API)

Database (MySQL) stores:

• Users
• Sessions
• Messages
• Leaderboards
• Admin settings
• Notifications

Optional future infrastructure:

• Redis (rate limiting)
• WebSocket server
• Analytics dashboard

---

# 8. Authentication and Authorization

## Roles

Two roles exist in the system:

| Role  | Permissions           |
| ----- | --------------------- |
| Admin | Full system control   |
| User  | Chat interaction only |

## Authentication

Users log in with:

• username/email
• password

Passwords stored using **bcrypt hashing**.

Authentication handled using **JWT tokens**.

## Acceptance Criteria

• Users cannot access admin routes
• Admins can access both monitoring and configuration tools
• Invalid credentials are rejected

---

# 9. User Chat Interface

Participants interact with the AI model through a chat UI.

Features:

• Prompt input box
• Response display area
• Chat history
• Remaining message count
• Session timer
• Challenge instructions
• System notifications from admins

Rules enforced by backend:

• Prompt limit per user
• Rate limiting
• Session timeout

Acceptance Criteria:

• User can send prompts until the configured limit
• System rejects prompts if limits exceeded
• Chat history persists during the session

---

# 10. Admin Dashboard

The admin dashboard provides monitoring and control capabilities.

Admins can view:

• Active users
• Prompt count per user
• Prompt timestamps
• Response logs
• Session progress
• Leaderboard rankings

Admins can control:

• Maximum messages per user
• Rate limits
• Challenge duration
• LLM provider/model
• Start or stop sessions

Admins may also **reset user sessions if needed**.

---

# 11. Admin Broadcast Notification System

Admins must be able to send **global notifications to all participants**.

Examples:

• "Round 1 Start"
• "Round 2 Begins"
• "5 Minutes Remaining"
• "Challenge Paused"
• "Final Round"

Notifications should appear instantly in the user interface.

Implementation options:

Option 1 (MVP): polling API

Option 2 (recommended): WebSockets

Notification properties:

• message
• timestamp
• sender (admin)
• priority

---

# 12. Competition Logic

Winners are determined using objective metrics.

Suggested scoring metrics:

• number of prompts used
• time taken
• whether the target output was achieved

Example rule set:

Winner = first participant to achieve target output.

Tie breaker:

1. fewer prompts used
2. lower completion time

All scoring inputs must be stored in the database.

---

# 13. Functional Requirements

## User Login

• login endpoint
• session creation
• role verification

## Chat System

• send prompt endpoint
• response retrieval
• message history retrieval

## Prompt Logging

For each prompt record:

• user_id
• session_id
• prompt
• response
• timestamps
• response latency
• success flag

## Admin Controls

Admins can change:

• message limits
• cooldown time
• challenge duration
• model provider

## Leaderboard

Leaderboard must show:

• participant ranking
• prompts used
• completion time
• status

---

# 14. Non‑Functional Requirements

## Performance

• Support ~20 concurrent users
• Prompt logging must be reliable

## Reliability

• System must handle LLM latency gracefully
• Failed prompts must still be logged

## Security

• password hashing
• role-based access
• API request validation

## Maintainability

• modular backend services
• LLM provider abstraction

---

# 15. Database Design

## users

id
name
email
password_hash
role
created_at

## sessions

id
session_name
start_time
end_time
status

## user_sessions

id
user_id
session_id
joined_at
completed_at
score

## messages

id
user_id
session_id
prompt_text
response_text
prompt_timestamp
response_timestamp
latency_ms

## admin_settings

id
max_messages_per_user
max_messages_per_minute
challenge_duration

## notifications

id
message
created_by
created_at

## audit_logs

id
actor_id
action_type
action_data

---

# 16. API Endpoints

Authentication:

POST /auth/login
POST /auth/logout

User Chat:

POST /chat/send
GET /chat/history

Admin APIs:

GET /admin/stats
GET /admin/users
POST /admin/settings

Notifications:

POST /admin/notify

Leaderboard:

GET /admin/leaderboard

---

# 17. UI Screens

## User Interface

1. User Login
2. Chat Dashboard
3. Challenge Instructions
4. Completion Screen

## Admin Interface

1. Admin Login
2. Admin Dashboard
3. Live Monitoring Panel
4. Leaderboard
5. Notification Broadcast Panel
6. Prompt Logs Viewer

---

# 18. Deployment Architecture

Server infrastructure:

Cloud VM

Services:

• Next.js frontend
• FastAPI backend
• MySQL database
• Ollama (optional)

Reverse proxy:

• Nginx

---

# 19. Event Workflow

## Before Event

Admins:

• configure challenge
• register users
• set limits

## During Event

Participants:

• login
• interact with AI

Admins:

• monitor prompts
• send notifications
• adjust limits

## After Event

Admins:

• review logs
• verify winner
• export results

---

# 20. Success Metrics

The platform is successful if:

• All participants can log in successfully
• Prompts are logged without data loss
• Admin dashboard reflects live activity
• Winner can be determined objectively

---

# 21. Final Recommendation

The system should be implemented using:

Frontend: **Next.js**
Backend: **FastAPI**
Database: **MySQL**
LLM Provider: **Ollama (initially) with API fallback support**

This architecture ensures the system can support a live event while remaining flexible for future expansion.

