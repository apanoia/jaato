# Project Structure Guide

This document provides an overview of the project's directory structure and architecture.

## Directory Layout

```
project/
├── src/                    # Source code
│   ├── components/         # UI components
│   ├── services/           # Business logic
│   ├── utils/              # Utility functions
│   └── types/              # Type definitions
├── tests/                  # Test files
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── fixtures/           # Test data
├── docs/                   # Documentation
├── scripts/                # Build and deployment scripts
└── config/                 # Configuration files
```

## Architecture Overview

### Core Components

1. **Services Layer**: Business logic and data operations
2. **Components Layer**: UI elements and views
3. **Utils Layer**: Shared utilities and helpers

### Data Flow

1. User input → Components
2. Components → Services (via events/calls)
3. Services → Data sources (APIs, databases)
4. Responses flow back up the chain

## Key Patterns

- **Dependency Injection**: Services are injected, not imported directly
- **Event-Driven**: Components communicate via events
- **Repository Pattern**: Data access is abstracted behind repositories
