# React Introduction

## What is React?

React is a JavaScript library for building user interfaces, maintained by Meta. It uses a component-based architecture where UI is broken into reusable pieces. React's declarative approach makes it easy to predict how the UI will look based on application state.

## JSX Syntax

JSX is a syntax extension for JavaScript that looks similar to HTML. It allows you to write HTML-like code in your JavaScript files. Under the hood, JSX gets transpiled to React.createElement() calls, making it easier to visualize your UI structure.

## Components and Props

Components are the building blocks of React applications. They accept inputs called props and return React elements that describe what should appear on screen. Components can be defined as functions or classes, with function components being the modern standard.

## State Management with useState

State represents data that changes over time in your component. The useState hook lets you add state to function components. When state changes, React re-renders the component to reflect the new UI, handling the DOM updates efficiently.

## Side Effects with useEffect

useEffect handles side effects in function components—things like data fetching, subscriptions, or DOM manipulation. It runs after render and can clean up after itself when components unmount, preventing memory leaks and stale data issues.

## Event Handling

React events are named using camelCase rather than lowercase. You pass functions as event handlers, and React provides synthetic events that work consistently across browsers. Common patterns include onClick, onChange, and onSubmit handlers.

## Conditional Rendering

Conditional rendering lets you display different UI based on state. You can use JavaScript conditionals like if statements, ternary operators, or logical AND (&&) operators to control what gets rendered.

## Lists and Keys

Rendering lists in React involves mapping over arrays and returning JSX. Keys help React identify which items have changed, are added, or removed. Using stable, unique keys as sibling identifiers is crucial for performance and correct updates.

## Forms in React

Forms in React work a bit differently because form elements naturally maintain their own state. Controlled components let React manage the form state, giving you predictable behavior and easier validation of user input before submission.

## Context API

Context provides a way to pass data through the component tree without manually passing props at every level. It's useful for global data like themes, user authentication, or language preferences that many components need access to.

## React Lifecycle (Class Components)

Before hooks, class components used lifecycle methods like componentDidMount, componentDidUpdate, and componentWillUnmount. Understanding these helps you read older React code and understand how hooks map to these lifecycle phases.

## Custom Hooks

Custom hooks let you extract component logic into reusable functions. They start with "use" and can call other hooks. This pattern helps share stateful logic between components without changing your component hierarchy.

## React Router

For multi-page applications in React, React Router handles client-side routing. It lets you define routes that map URL paths to components, enabling navigation without full page reloads and preserving application state during transitions.
