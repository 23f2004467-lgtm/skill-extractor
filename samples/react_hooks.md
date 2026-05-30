****In React, Hooks are functions that allow you to manage**** state and perform side effects without the involvement of class components. Hooks were introduced in v16.8 of React and they can be accessed only through functional components but not through class components (Hooks were specifically designed for that). Hooks allow you to "hook into" React state and lifecycle features from functional components.

## Prerequisites

* [ReactJs](https://www.geeksforgeeks.org/reactjs/react/)
* [React Components](https://www.geeksforgeeks.org/reactjs/reactjs-components/)
* [React props](https://www.geeksforgeeks.org/reactjs/reactjs-methods-as-props/)
* [React lifecycle methods](https://www.geeksforgeeks.org/reactjs/reactjs-lifecycle-components/)

Table of Content

* [What are React Hooks?](#what-are-react-hooks)
* [Why React Hooks?](#why-react-hooks)
* [Traditional way of managing state and side effects](#traditional-way-of-managing-state-and-side-effects)
* [Rules of React Hooks](#rules-of-react-hooks)
* [Types of Hooks](#types-of-hooks)
* [Custom Hooks](#custom-hooks)
* [Features of React Hooks](#features-of-react-hooks)

## What are React Hooks?

React Hooks are functions that allow you to use state and other React features without writing a class. Prior to Hooks, stateful logic in React components was primarily encapsulated in class components using the `setState` method. Hooks provide a more functional approach to state management and enable the use of lifecycle methods, context, and other React features in functional components.

****Note:**** React Hooks can't be used inside of class components.

## Why React Hooks?

* ****Simplified Logic:**** Hooks eliminate the need for class components, reducing boilerplate code and making components easier to understand and maintain.
* ****Reusability:**** With Hooks, you can extract stateful logic into custom hooks and reuse it across multiple components, promoting code reuse and modularity.
* ****Improved Performance:**** Hooks optimize the rendering process by allowing React to memoize the state and only re-render components when necessary.
* ****Better Testing:**** Functional components with Hooks are easier to test compared to class components, as they are purely based on input and output.

## Traditional way of managing state and side effects

Managing state variable's value through class components traditionally, Now, let us implement an incrementor that increments the number by clicking a button.

****Example:**** Implementation to show managing state and side effects.

JavaScript

```` ```
import React, { Component } from 'react'

export default class Incrementor extends Component {
          constructor(){
            super();    
            this.state={
                count:0    
            };
          }
          increment = ()=>{
            this.setState({
                count: this.state.count + 1
            });
          }
  render() {
    return (
      <div>
          <h1>{this.state.count}</h1>
          <button onClick={this.increment}>
              increment
          </button>
      </div>
    )
  }
}
``` ````

****Output:****

![count-incrementor-2](https://media.geeksforgeeks.org/wp-content/uploads/20240410122441/count-incrementor-2.gif)

Managing side effects through a class component traditionally, Side effects these are the operations that are performed to fetch data or to manipulate DOM are known as side effects.Now, let us perform a side effect by changing the title of the document after every increment of the count value.

****Example:**** Implementation to show side effects with an example.

JavaScript

```` ```
import React, { Component } from 'react'

export default class Incrementor extends Component {
    constructor() {
        super();
        this.state = {
            count: 0
        };
    }
    incrementor = () => {
        this.setState({
            count: this.state.count + 1
        });
    }
    componentDidUpdate() {
        document.title =
            `Count incremented to ${this.state.count}`;
    }
    render() {
        return (
            <div>
                <h1>{this.state.count}</h1>
                <button onClick={this.incrementor}>
                    increment
                </button>
            </div>
        )
    }
}
``` ````

****Output:****

![lm-count](https://media.geeksforgeeks.org/wp-content/uploads/20240410120849/lm-count.gif)

## Rules of React Hooks

* Hooks should be called only at the top level.
* Don't call hooks conditonally and inside a loop.
* Hooks should be called only in a functional component but not through regular JavaScript functions.

## Types of Hooks

State Hook allows us to manage component state directly within functional components, without the necessity of class components. State in React refers to any data or property that is dynamic and can change overtime.

### [****useState :****](https://www.geeksforgeeks.org/reactjs/reactjs-usestate-hook/)

It manages state in functional components by providing a state variable and a function to update it, enabling dynamic UI updates.

****Syntax**** :

```
 const [stateVariable, setStateFunction] = useState(initialStateValue)
```

****Example:**** Implementation to the use show the use of usestate hook.

JavaScript

```` ```
import React from 'react'
import {useState} from 'react';

export default function Incrementor() {
const [count,setCount]=useState(0);
    const  increment=()=>{
        setCount(count+1);
    }
  return (
    <>
        <h1>{count}</h1>
        <button onClick={increment}>increment</button>
    </>
  )
}
``` ````

****Output****:

![count-incrementor-2](https://media.geeksforgeeks.org/wp-content/uploads/20240410122441/count-incrementor-2.gif)

### [****useEffect :****](https://www.geeksforgeeks.org/reactjs/reactjs-useeffect-hook/)

It handles side effects like data fetching, subscriptions, or DOM manipulation in functional components after rendering.

****Syntax:****

```
useEffect(() => {  
  // Effect code  
  return () => {  
    // Cleanup code  
  };  
}, [dependencies]);
```

****Example:****

JavaScript

```` ```
import React from "react";
import { useState, useEffect } from "react";

export default function Incrementor() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    document.title =  `Count incremented to ${count}`;
  });
  const increment = () => {
    setCount(count + 1);
  };
  return (
    <>
      <h1>{count}</h1>
      <button onClick={increment}>increment</button>
    </>
  );
}
``` ````

****Output:****

![lm-count](https://media.geeksforgeeks.org/wp-content/uploads/20240410120849/lm-count.gif)

### [****useReducer****](https://www.geeksforgeeks.org/reactjs/reactjs-usereducer-hook/) ****:****

`useReducer` is a Hook in React used for state management. It accepts a reducer function and an initial state, returning the current state and a dispatch function. The dispatch function is used to trigger state updates by passing an action object to the reducer. This pattern is especially useful for managing complex state logic and interactions in functional components.

****Syntax:****

```
const [state, dispatch] = useReducer(reducer, initialState);
```

****Example**** :

JavaScript

```` ```
import React, { useReducer } from "react";
 
function reducer(state, action) {
  switch (action) {
    case "add":
      return state + 1;
    case "subtract":
      return state - 1;
    default:
      throw new Error("Unexpected action");
  }
};
 
function MyComponent() {
  const [count, dispatch] = useReducer(reducer, 0);
  return (
    <>
      <h2>{count}</h2>
      <button onClick={() => dispatch("add")}>
        add
      </button>
      <button onClick={() => dispatch("subtract")}>
        subtract
      </button>
    </>
  );
};
 
export default MyComponent;
``` ````

****Output:****

![cdws](https://media.geeksforgeeks.org/wp-content/uploads/20240417160114/cdws.gif)

### [****useLayoutEffect :****](https://www.geeksforgeeks.org/reactjs/reactjs-uselayouteffect-hook/)

`useLayoutEffect` is a Hook in React similar to `useEffect`, but it synchronously runs after all DOM mutations. It's useful for operations that need to be performed after the browser has finished painting but before the user sees the updates.

****Note :**** It is recommended to use "useEffect" over "useLayoutEffect" whenever possible , because "useLayoutEffect" effects the performance of the application.

****Example**** :

JavaScript

```` ```
import React from "react";
import { useState, useLayoutEffect } from "react";

export default function MyComponent() {
    const [count, setCount] = useState(0);

    const increment = () => {
        setCount(count + 1);
    };

    useLayoutEffect(() => {
        console.log("Count is Incremented");
    }, [count]);

    return (
        <>
            <h1>{count}</h1>
            <button onClick={increment}>
                Increment
            </button>
        </>
    );
}
``` ````

****Output:****

![cqa](https://media.geeksforgeeks.org/wp-content/uploads/20240417160536/cqa.gif)

### [u****seContext :****](https://www.geeksforgeeks.org/reactjs/reactjs-usecontext-hook/)

`useContext` simplifies data sharing by allowing components to access context values without manual prop drilling. It enables passing data or state through the component tree effortlessly.

****Syntax:****

```
const value = useContext(MyContext);
```

### [****useCallback**** :](https://www.geeksforgeeks.org/reactjs/react-js-usecallback-hook/)

`useCallback` memoizes callback functions, preventing unnecessary re-renders of child components when the callback reference remains unchanged. It optimizes performance by avoiding the recreation of callbacks on each render.

****Syntax:****

```
const memoizedCallback = useCallback(() => {  
  // Callback logic  
}, [dependencies]);
```

### [****useMemo**** :](https://www.geeksforgeeks.org/reactjs/react-js-usememo-hook/)

`useMemo` memoizes function values, preventing unnecessary re-renders due to changes in other state variables. It's used to optimize performance by memoizing expensive calculations or derived values.

****Syntax:****

```
const memoizedValue = useMemo(() => {  
  // Value computation logic  
}, [dependencies]);
```

## [Custom Hooks](https://www.geeksforgeeks.org/reactjs/reactjs-custom-hooks/)

Custom Hooks in React allows you to create your own hook and helps you to reuse that hook's functionality across various functional components. A custom hook can be created by naming a JavaScript function with the prefix "use".

****Note :**** If the JavaScript function is not named with the prefix "use", React considers it as a regular JavaScript function.

****Syntax :****

```
function useCustomHook() {  
  //code to be executed  
 }
```

****Example :**** Implementation to show the use the sue of custom hooks.

JavaScript

```` ```
//useCustomHook.js

import { useState} from "react";

export  function useCustomHook(value) {
  const [count,setCount]=useState(value);
  
  const increment = () => {
    setCount(count + 1);
  };
  return{
    count,
    increment,
};
};
``` ````
JavaScript

```` ```
// FirstComponent.js

import {useCustomHook} from "./useCustomHook";

export  default function FirstComponent(){
    const {count,increment} = useCustomHook(0);
    
  return (
    <>
      <h1>{count}</h1>
      <button onClick={increment}>Increment</button>
    </>
  );
};
``` ````
JavaScript

```` ```
// SecondComponent.js

import {useCustomHook} from "./useCustomHook";

export  default function SecondComponent(){
    const {count,increment} = useCustomHook(0);
    
  return (
    <>
      <h1>{count}</h1>
      <button onClick={increment}>Increment</button>
    </>
  );
};
``` ````

****Output :****

![CustomHooks](https://media.geeksforgeeks.org/wp-content/uploads/20240417125819/CustomHooks.gif)

## Features of React Hooks

* ****Functional Components:**** Allow using state and lifecycle methods in functional components without needing class syntax.
* ****Reusability:**** Promote reusability of stateful logic by encapsulating it in custom hooks.
* ****Simplified Lifecycle:**** Offer useEffect hook for handling side effects, replacing componentDidMount, componentDidUpdate, and componentWillUnmount.
* ****Clean Code:**** Reduce boilerplate and improve readability by removing class components and HOCs.
* ****Improved Performance:**** Optimize rendering performance by memoizing values with useMemo and callbacks with useCallback.
* ****Easier Testing:**** Simplify unit testing of components with hooks by decoupling logic from the UI.