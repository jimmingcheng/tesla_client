import inspect
from typing import get_type_hints


def format_agent_api_doc(cls: type, whitelisted_members: list[str] | None = None) -> str:
    lines = [f'class {cls.__name__}:']

    class_doc = inspect.getdoc(cls)
    if class_doc:
        lines.append(f'    """{class_doc}"""\n')

    annotations = get_type_hints(cls, localns=cls.__dict__)  # type: ignore

    def get_type_name(annotation):
        """Helper function to extract only the class name from a type hint."""
        if annotation is None or annotation is inspect.Signature.empty:
            return "None"
        if isinstance(annotation, type):
            return annotation.__name__
        if hasattr(annotation, "__origin__"):  # Handles generics like `list[Vehicle]`
            origin = annotation.__origin__.__name__
            args = ", ".join(get_type_name(arg) for arg in annotation.__args__)
            return f"{origin}[{args}]"
        return str(annotation)

    if not whitelisted_members:
        whitelisted_members = list(annotations.keys()) + [
            name for name, _ in inspect.getmembers(cls) if not name.startswith("_")
        ]

    for name in whitelisted_members:
        if hasattr(cls, name):
            attr = getattr(cls, name)
            if inspect.isfunction(attr) or inspect.ismethod(attr):  # If it's a function/method
                sig = inspect.signature(attr)
                params = [
                    f"{param.name}: {get_type_name(param.annotation)}"
                    if param.annotation is not inspect.Parameter.empty
                    else param.name
                    for param in sig.parameters.values()
                ]
                return_type = f" -> {get_type_name(sig.return_annotation)}"
                line = f'    def {name}({", ".join(params)}){return_type}'
            else:  # If it's a variable
                line = f'    {name}: {type(attr).__name__}'
            lines.append(line)
        elif name in annotations:
            lines.append(f'    {name}: {get_type_name(annotations[name])}')

    return "\n".join(lines)
