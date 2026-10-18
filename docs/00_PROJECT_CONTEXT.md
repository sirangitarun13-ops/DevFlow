# DevFlow Project Context

## Project overview

DevFlow is a self-contained, web-based SDLC analytics platform for centralizing software project artifacts. It is intended to organize projects, requirements, sprints, tasks, bugs, test cases, reports, and the traceability relationships between them. Its central capability is the Requirement Change Impact Analysis (RCIA) Engine, which is intended to identify artifacts affected by a requirement change.

## Problem statement

Project-management tools can store software development information while still requiring teams to manually determine how requirement changes affect connected tasks, developers, bugs, test cases, and sprint schedules. Manual impact analysis can lead to missed dependencies, delayed communication, inefficient planning, reduced visibility, and delivery risk.

## Objectives

- Develop an integrated SDLC management platform.
- Maintain end-to-end traceability across requirements, tasks, bugs, test cases, and sprints.
- Automate requirement change impact analysis.
- Improve visibility with software engineering analytics and interactive dashboards.
- Support Agile planning and monitoring.
- Improve collaboration among project managers, developers, testers, and clients.

## Main features

The SRS defines these functional areas: authentication and role management; project, requirement, sprint, task, bug, and test-case management; requirement traceability; RCIA; analytics dashboards; and PDF report generation.

## User roles

| Role | SRS responsibility |
| --- | --- |
| Admin | Manage users, roles, and platform-level configuration. |
| Project Manager | Manage projects, monitor progress, review RCIA output, and generate reports. |
| Team Lead | Plan sprints, assign tasks, coordinate team members, and evaluate impact results. |
| Developer | Update assigned work, view linked requirements, respond to impacted work, and add comments. |
| Tester | Manage test cases, report bugs, link test cases to requirements, and verify affected artifacts. |
| Client | View permitted project status, reports, and selected dashboard information. |

## Technology stack

The required stack is React with Tailwind CSS for the frontend; FastAPI REST services for the backend; PostgreSQL for persistent data; JWT for authentication and role-based authorization; React Flow for traceability graphs; and Recharts for dashboard charts. Client-server communication uses REST-style JSON over HTTP or HTTPS.

## Constraints

- DevFlow is a web-based client-server application.
- The selected FastAPI, PostgreSQL, React, Tailwind CSS, JWT, React Flow, and Recharts technologies are required by the SRS.
- The workflow must support Agile concepts including sprints, tasks, requirements, bugs, and team assignment.
- The initial release does not require external project-management-platform integration.
- Meaningful RCIA depends on teams maintaining traceability links between requirements and related artifacts.
- Production deployment should use HTTPS to protect tokens and project data in transit.

## Exclusions

The following are future scope rather than baseline functionality: external integrations (including GitHub), AI-assisted requirement summarization, automatic test-case suggestion, predictive project risk analysis, and daily database backup.
