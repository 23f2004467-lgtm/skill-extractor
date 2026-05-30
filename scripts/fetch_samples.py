"""
scripts/fetch_samples.py

One-time scraping utility to fetch GFG course modules and convert to markdown.
"""

import os
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md


# GFG URLs to fetch
URLS = {
    "python_oops": "https://www.geeksforgeeks.org/python-oops-concepts/",
    "sql_joins": "https://www.geeksforgeeks.org/sql-joins-inner-left-right-and-full-joins/",
    "react_hooks": "https://www.geeksforgeeks.org/introduction-to-react-hooks/",
    "linked_lists": "https://www.geeksforgeeks.org/linked-list-data-structure/",
}

# User-Agent to mimic a real browser
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Selectors to try, in order
CONTENT_SELECTORS = ["article", ".text", ".content", "main", ".article-content"]

# Tags to strip before conversion
TAGS_TO_STRIP = ["nav", "footer", "script", "style", "noscript", "iframe", "aside"]


def fetch_url(url: str) -> Optional[str]:
    """Fetch a URL and return the HTML content, or None if it fails."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  ✗ Failed to fetch {url}: {e}")
        return None


def extract_article_content(html: str) -> Optional[str]:
    """Extract the main article content from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Strip out unwanted tags
    for tag in TAGS_TO_STRIP:
        for element in soup.find_all(tag):
            element.decompose()

    # Try each selector
    for selector in CONTENT_SELECTORS:
        element = soup.select_one(selector)
        if element:
            return str(element)

    # Fallback: return body content
    body = soup.find("body")
    if body:
        return str(body)

    return None


def html_to_markdown(html: str) -> str:
    """Convert HTML to markdown using markdownify."""
    return md(html, heading_style="ATX")


def save_markdown(content: str, slug: str) -> Path:
    """Save markdown content to samples/<slug>.md and return the path."""
    samples_dir = Path(__file__).parent.parent / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    output_path = samples_dir / f"{slug}.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_stub(slug: str) -> Path:
    """Write a hand-crafted markdown stub when scraping fails."""
    stubs = {
        "python_oops": """# Python OOPs Concepts

## Classes and Objects

Object-Oriented Programming (OOP) is a programming paradigm based on the concept of objects, which can contain data and code. In Python, everything is an object. A class is a blueprint for creating objects, defining the properties and behaviors that the objects will have.

Objects are instances of classes. When you create an object from a class, you're instantiating that class. Each object has its own set of attributes and methods, independent of other objects of the same class.

## Encapsulation

Encapsulation is the bundling of data and methods that work on that data within a single unit—usually a class. In Python, encapsulation is achieved through the use of private and protected attributes, denoted by single or double underscores.

Private attributes start with double underscores and cannot be accessed directly from outside the class. Protected attributes start with a single underscore and indicate that they should not be accessed directly, though Python doesn't enforce this.

## Inheritance

Inheritance allows a class to acquire the properties and methods of another class. The class that inherits is called the child or subclass, and the class being inherited from is the parent or superclass.

Python supports multiple inheritance, meaning a class can inherit from more than one parent class. The `super()` function allows you to call methods from the parent class, enabling method overriding and extension.

## Polymorphism

Polymorphism means "many forms" and allows objects of different classes to be treated as objects of a common superclass. The most common use is method overriding, where a subclass provides a specific implementation of a method defined in its superclass.

Duck typing is Python's approach to polymorphism—if it walks like a duck and quacks like a duck, it's a duck. This means you don't need explicit interfaces; if an object has the required methods, it can be used regardless of its class.

## Abstraction

Abstraction hides complex implementation details while exposing only necessary features. Abstract base classes (ABCs) in Python define abstract methods that must be implemented by subclasses, ensuring a consistent interface.

The `abc` module provides tools for creating abstract base classes. Using `@abstractmethod` decorator, you can declare methods that subclasses must implement, enforcing a contract while hiding implementation details.

## Special Methods (Magic Methods)

Python uses special methods (dunder methods) to define how objects behave with built-in operations. These include `__init__` for initialization, `__str__` for string representation, and `__eq__` for equality comparison.

Other important magic methods include `__len__`, `__getitem__`, `__setitem__`, and `__call__`. These methods allow your objects to work seamlessly with Python's syntax and built-in functions.
""",
        "sql_joins": """# SQL Joins - Inner, Left, Right, and Full Joins

## Understanding Joins

SQL joins are used to combine rows from two or more tables based on a related column between them. Joins are fundamental to relational databases, allowing you to query related data spread across multiple tables efficiently.

The most common type of join is the inner join, which returns only rows where there's a match in both tables. Understanding how different joins work is crucial for writing effective queries and avoiding data loss or duplication.

## INNER JOIN

INNER JOIN returns records that have matching values in both tables. It's the default join type in SQL and creates a new table by combining columns from both tables where the join condition is satisfied.

For example, joining a customers table with an orders table on customer_id will return only customers who have placed orders, and only orders that belong to existing customers. Records without matches are excluded.

## LEFT JOIN (LEFT OUTER JOIN)

LEFT JOIN returns all records from the left table and matched records from the right table. When there's no match, NULL values are returned for columns from the right table. The "left" table is the one mentioned first in the join.

This join is useful when you want all records from one table regardless of whether they have related records in another table. For example, all customers even if they haven't placed any orders yet.

## RIGHT JOIN (RIGHT OUTER JOIN)

RIGHT JOIN returns all records from the right table and matched records from the left table. When there's no match, NULL values are returned for columns from the left table. This is essentially the mirror of LEFT JOIN.

RIGHT JOIN is less commonly used than LEFT JOIN because you can usually achieve the same result by reversing the table order and using LEFT JOIN, which many developers find more intuitive.

## FULL JOIN (FULL OUTER JOIN)

FULL JOIN returns all records when there's a match in either table. It combines the results of LEFT and RIGHT joins—all records from both tables, with NULLs filling in where there's no match.

Not all database systems support FULL JOIN. MySQL, for example, doesn't support it directly, but you can simulate it using UNION of LEFT JOIN and RIGHT JOIN.

## CROSS JOIN

CROSS JOIN returns the Cartesian product of the two tables—every row from the first table paired with every row from the second table. It doesn't require a join condition and can produce very large result sets.

Use CROSS JOIN carefully as it can generate massive amounts of data. It's useful for generating all possible combinations, such as creating all possible product variations or pairing every customer with every product.

## Self Joins

A self join joins a table to itself. This is useful when a table has a hierarchical relationship, such as employees and managers where both are in the same table. You use table aliases to distinguish the two instances of the table.

For example, to find each employee and their manager, you'd join the employees table to itself where the manager_id of one record equals the employee_id of another.

## Join Performance

Join performance can be impacted by several factors. Proper indexing on join columns is crucial for fast joins. The order of tables in joins can matter, especially for outer joins, and understanding how your database optimizes joins can help you write better queries.

Database query planners usually optimize join order automatically, but understanding the mechanics helps you write queries that execute efficiently, especially with large datasets.
""",
        "react_hooks": """# Introduction to React Hooks

## What are Hooks?

React Hooks are functions that let you use state and other React features in functional components without writing a class. Introduced in React 16.8, hooks solve many problems that existed with class components, including logic reuse and complex state management.

Before hooks, you needed class components to use state or lifecycle methods. This made code reuse difficult and led to "wrapper hell" with higher-order components and render props.

## useState Hook

The useState hook lets you add state to functional components. It returns an array with two elements: the current state value and a function to update it. When state changes, React re-renders the component.

You can use useState multiple times in a single component to track different pieces of state. The update function can be used with either a new value or a function that computes the new state from the old state.

## useEffect Hook

useEffect lets you perform side effects in functional components—things like data fetching, subscriptions, or manually changing the DOM. It runs after every render by default, but you can control when it runs using the dependency array.

The dependency array specifies which values the effect depends on. When those values change, React re-runs the effect. If you pass an empty array, the effect runs only once after the initial render, similar to componentDidMount.

## useContext Hook

useContext lets you consume context values without nesting Consumer components. It accepts a context object and returns the current context value for that context. When the nearest Provider updates, this hook will trigger a re-render with the latest context value.

Context is designed for sharing data that can be considered global to a component tree, like the current authenticated user, theme, or language preference.

## useReducer Hook

useReducer is an alternative to useState for complex state logic. It accepts a reducer function and an initial state, returning the current state and a dispatch method. It's predictable and easier to test than useState for complex state transitions.

The reducer function takes the current state and an action, then returns the new state. Actions are typically objects with a type property and optional payload. This pattern is familiar from Redux and similar libraries.

## useCallback Hook

useCallback returns a memoized callback function that only changes when its dependencies change. This is useful for passing callbacks to child components that rely on reference equality to prevent unnecessary renders.

Without useCallback, a new function would be created on every render, causing child components that receive it as a prop to re-render even if they haven't actually changed.

## useMemo Hook

useMemo returns a memoized value that only recomputes when its dependencies change. This is useful for expensive calculations that you don't want to repeat on every render.

Use useMemo sparingly—only when you've measured a performance problem. Overusing it can make code less readable and might even hurt performance due to the overhead of dependency tracking.

## useRef Hook

useRef returns a mutable ref object whose `.current` property is initialized to the passed argument. The ref persists across re-renders and doesn't trigger a re-render when changed, unlike state.

Refs are useful for directly accessing DOM elements, storing mutable values that don't affect rendering, and integrating with non-React libraries that weren't designed for React's mental model.

## Custom Hooks

Custom hooks let you extract component logic into reusable functions. They're regular JavaScript functions that can call other hooks, and their name must start with "use" by convention.

Custom hooks are a powerful way to share stateful logic between components without changing your component hierarchy or resorting to higher-order components and render props.

## Rules of Hooks

Hooks have two important rules: only call them at the top level (not inside loops, conditions, or nested functions), and only call them from React function components or custom hooks.

These rules are enforced by the ESLint plugin `eslint-plugin-react-hooks`. Breaking them can cause bugs because React relies on the order of hook calls to correctly associate state with components.
""",
        "linked_lists": """# Linked List Data Structure

## What is a Linked List?

A linked list is a linear data structure where elements are stored in nodes, and each node points to the next node in the sequence. Unlike arrays, linked lists don't store elements in contiguous memory locations—each node contains data and a reference (or link) to the next node.

The first node is called the head, and the last node points to null, indicating the end of the list. This structure allows efficient insertion and deletion at any position, unlike arrays which require shifting elements.

## Singly Linked Lists

In a singly linked list, each node has only one pointer to the next node. Operations like traversal are straightforward—start at the head and follow next pointers until you reach null.

Insertion at the beginning is O(1) because you only need to update the head pointer. Insertion or deletion at other positions requires traversal, making those operations O(n) in the worst case.

## Doubly Linked Lists

A doubly linked list has nodes with two pointers: next and previous. This allows traversal in both directions and makes certain operations easier, like deleting a node when you only have a reference to it.

The trade-off is increased memory overhead for storing the previous pointer, and more complex code with more edge cases to handle, such as updating both next and previous pointers during insertion and deletion.

## Circular Linked Lists

In a circular linked list, the last node points back to the head instead of null. This can be singly or doubly circular. Circular lists are useful for applications that require cycling through elements repeatedly, like implementing round-robin scheduling.

Traversal in a circular list requires care—you need to detect when you've completed a full cycle to avoid infinite loops. This is typically done by comparing the current node to the starting point.

## Common Operations

Insertion involves creating a new node and adjusting pointers to include it in the list. At the head, update the new node's next to current head, then update head to the new node. At other positions, find the node before the insertion point and adjust its next pointer.

Deletion requires finding the node to delete and the node before it. Update the previous node's next pointer to skip the deleted node. If deleting the head, simply move head to the next node.

## Searching a Linked List

Searching in a linked list is O(n) because you must traverse from the head, checking each node's value. This is slower than array binary search but comparable to linear search in arrays.

The advantage is that linked lists handle frequent insertions and deletions more efficiently than arrays, especially when the size changes frequently or elements need to be inserted at random positions.

## Linked List vs Arrays

Arrays provide O(1) random access by index, while linked lists require O(n) traversal. Arrays have better cache locality due to contiguous memory, making them faster for sequential access.

However, linked lists excel at insertion and deletion operations—O(1) at known positions compared to O(n) for arrays which require shifting elements. Linked lists also don't require pre-allocation and can grow dynamically.

## Common Applications

Linked lists are used in many real-world applications. Undo/redo functionality in text editors often uses doubly linked lists. Web browsers use them for back/forward navigation history.

They're also used in implementing other data structures like stacks, queues, and even hash maps for collision resolution through chaining. Graph adjacency lists frequently use linked list variants.

## Memory Considerations

Each node in a linked list requires memory for data plus pointer(s), leading to overhead that doesn't exist with arrays. For large datasets, this overhead can be significant.

However, linked lists don't require contiguous memory allocation, which can be advantageous in memory-constrained environments or when dealing with data that grows and shrinks unpredictably.
""",
    }

    content = stubs.get(slug, "")
    return save_markdown(content, slug)


def main():
    """Fetch all URLs and save as markdown files."""
    samples_dir = Path(__file__).parent.parent / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching GFG course modules...")
    print("=" * 50)

    for slug, url in URLS.items():
        print(f"\nFetching {url}...")

        html = fetch_url(url)
        if html is None:
            print(f"  ✗ Failed to fetch, writing stub for {slug}")
            path = write_stub(slug)
            print(f"  → Created stub: {path}")
            continue

        article_html = extract_article_content(html)
        if article_html is None:
            print(f"  ✗ Failed to extract content, writing stub for {slug}")
            path = write_stub(slug)
            print(f"  → Created stub: {path}")
            continue

        markdown = html_to_markdown(article_html)
        if len(markdown.strip()) < 100:
            print(f"  ✗ Content too short ({len(markdown)} chars), writing stub for {slug}")
            path = write_stub(slug)
            print(f"  → Created stub: {path}")
            continue

        path = save_markdown(markdown, slug)
        print(f"  ✓ Saved: {path} ({len(markdown)} characters)")

    print("\n" + "=" * 50)
    print("Summary:")
    for slug in URLS.keys():
        md_path = samples_dir / f"{slug}.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8")
            print(f"  {slug}.md: {len(content)} characters")
        else:
            print(f"  {slug}.md: MISSING")


if __name__ == "__main__":
    main()
