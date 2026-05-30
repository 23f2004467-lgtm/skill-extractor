Object Oriented Programming empowers developers to build modular, maintainable and scalable applications. OOP is a way of organizing code that uses objects and classes to represent real-world entities and their behavior. In OOP, object has attributes thing that has specific data and can perform certain actions using methods.

* Organizes code into classes and objects.
* Supports encapsulation to group data and methods together.
* Enables inheritance for reusability and hierarchy.
* Allows polymorphism for flexible method implementation.

![Python OOPs ](https://media.geeksforgeeks.org/wp-content/uploads/20230818181616/Types-of-OOPS-2.gif)

Python OOPs Concepts

## Class

A class is a collection of objects. [Classes](https://www.geeksforgeeks.org/python/python-classes-and-objects/) are blueprints for creating objects. A class defines a set of attributes and methods that the created objects (instances) can have.  

* Classes are created by keyword class.
* Attributes are the variables that belong to a class.
* Attributes are always public and can be accessed using the dot (.) operator. ****Example:**** Myclass.Myattribute

### Creating a Class

Here, class keyword indicates that we are creating a class followed by name of the class (Dog in this case).

Python

```` ```
class Dog:
    species = "Canine"  # Class attribute

    def __init__(self, name, age):
        self.name = name  # Instance attribute
        self.age = age  # Instance attribute
``` ````

****Explanation:****

* class Dog: creates a class named Dog, which acts as a blueprint for dog objects.
* species is a class attribute, meaning it is shared by all instances of the class.
* [\_\_init\_\_()](https://www.geeksforgeeks.org/python/__init__-in-python/) is a constructor method that runs automatically when a new object is created. It is used to initialize object data.
* [self](https://www.geeksforgeeks.org/python/self-in-python-class/) refers to the current object, allowing each object to store and access its own data.
* self.name and self.age are instance attributes, unique to each Dog object created from the class.

## Objects

An [Object](https://www.geeksforgeeks.org/python/python-object/) is an instance of a Class. It represents a specific implementation of the class and holds its own data. An object consists of:

* State: represented by the attributes and reflects the properties of an object.
* Behavior: represented by the methods of an object and reflects the response of an object to other objects.
* Identity: gives a unique name to an object and enables one object to interact with other objects.

### Creating Object

Creating an object involves instantiating a class to create a new instance of that class. This process is also referred to as object instantiation.

Python

```` ```
class Dog:
    species = "Canine"  # Class attribute

    def __init__(self, name, age):
        self.name = name  # Instance attribute
        self.age = age  # Instance attribute

# Creating an object of the Dog class
dog1 = Dog("Buddy", 3)
print(dog1.name) 
print(dog1.species)
``` ````

**Output**

```
Buddy
Canine
```

****Explanation:****

* ****dog1 = Dog("Buddy", 3):**** Creates an object of the Dog class with name as "Buddy" and age as 3.
* ****dog1.name:**** Accesses the instance attribute name of the dog1 object.
* ****dog1.species:**** Accesses the class attribute species of the dog1 object.

## Four Pillars of OOP

Four Pillars of Object-Oriented Programming (OOP) form the foundation for designing structured, reusable and maintainable software.

### 1. Inheritance

[Inheritance](https://www.geeksforgeeks.org/python/inheritance-in-python/) allows a class (child class) to acquire properties and methods of another class (parent class). It supports hierarchical classification and promotes code reuse.

![animal_class](https://media.geeksforgeeks.org/wp-content/uploads/20260512143915187414/animal_class-660.webp)

Inheritance in Python

### 2. Polymorphism

[Polymorphism](https://www.geeksforgeeks.org/python/polymorphism-in-python/) means "same operation, different behavior." It allows functions or methods with the same name to work differently depending on the type of object they are acting upon.

The flowchart below represents the different types of polymorphism, showing how a single interface can exhibit multiple behaviors at compile-time and run-time.

![polymorphism_in_python](https://media.geeksforgeeks.org/wp-content/uploads/20260122110806427695/polymorphism_in_python.webp)

Types of Polymorphism

### 3. Encapsulation

[Encapsulation](https://www.geeksforgeeks.org/python/encapsulation-in-python/) is the bundling of data (attributes) and methods (functions) within a class, restricting access to some components to control interactions. A class is an example of encapsulation as it groups together member functions, variables and other related data in a single unit.

![encapsulation_in_python](https://media.geeksforgeeks.org/wp-content/uploads/20260512144120280854/encapsulation_in_python-660.webp)

Encapsulation in Python

### 4. Data Abstraction

[Abstraction](https://www.geeksforgeeks.org/python/data-abstraction-in-python/) hides the internal implementation details while exposing only the necessary functionality. It helps focus on "what to do" rather than "how to do it."

![data_abstraction](https://media.geeksforgeeks.org/wp-content/uploads/20260520170521089325/data_abstraction.webp)

Data Abstraction in Python

### Related Articles:

* [Constructors](https://www.geeksforgeeks.org/python/constructors-in-python/)
* [Static Method](https://www.geeksforgeeks.org/python/python-staticmethod/)
* [Operator Overloading](https://www.geeksforgeeks.org/python/operator-overloading-in-python/)