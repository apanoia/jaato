# Coding Standards

This document outlines the coding standards and best practices for the project.

## General Principles

1. **Readability First**: Code is read far more often than it's written
2. **Consistency**: Follow established patterns in the codebase
3. **Simplicity**: Prefer simple solutions over clever ones

## Naming Conventions

### Python
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`

### JavaScript/TypeScript
- Classes: `PascalCase`
- Functions/variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `#privateField` or `_underscore`

## Documentation

- All public functions must have docstrings
- Complex logic should have inline comments explaining "why"
- README files for each major module

## Testing

- Write tests for new functionality
- Aim for meaningful coverage, not just line coverage
- Use descriptive test names that explain the scenario

## Error Handling

- Catch specific exceptions, not bare `except:`
- Log errors with appropriate context
- Provide meaningful error messages to users
