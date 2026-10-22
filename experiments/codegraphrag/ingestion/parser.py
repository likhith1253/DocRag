import tree_sitter
from tree_sitter import Language, Parser
from typing import Dict, Any, List

# Load languages
try:
    import tree_sitter_python
    PY_LANGUAGE = Language(tree_sitter_python.language())
except ImportError:
    PY_LANGUAGE = None

try:
    import tree_sitter_javascript
    JS_LANGUAGE = Language(tree_sitter_javascript.language())
except ImportError:
    JS_LANGUAGE = None

try:
    import tree_sitter_typescript
    TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
    TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
except ImportError:
    TS_LANGUAGE = None
    TSX_LANGUAGE = None

def get_parser(language: str) -> Parser:
    """
    Get a tree-sitter parser for the given language.
    """
    if language == 'python' and PY_LANGUAGE:
        return Parser(PY_LANGUAGE)
    elif language == 'javascript' and JS_LANGUAGE:
        return Parser(JS_LANGUAGE)
    elif language == 'typescript' and TS_LANGUAGE:
        return Parser(TS_LANGUAGE)
    elif language == 'tsx' and TSX_LANGUAGE:
        return Parser(TSX_LANGUAGE)
    return None

def parse_code(code: str, language: str) -> Dict[str, Any]:
    """
    Parse source code to extract classes, functions, imports, and calls.
    
    Args:
        code: The source code string.
        language: The language identifier.
        
    Returns:
        A dict containing lists of classes, functions, imports, and calls.
    """
    res = {
        "classes": [],
        "functions": [],
        "imports": [],
        "calls": []
    }
    
    parser = get_parser(language)
    if not parser:
        return res
        
    tree = parser.parse(bytes(code, "utf-8"))
    root = tree.root_node
    
    class_stack = []
    function_stack = []
    
    def get_node_text(node) -> str:
        return node.text.decode('utf-8', errors='ignore')
        
    def traverse(node):
        nonlocal class_stack, function_stack
        
        node_type = node.type
        pushed_class = False
        pushed_func = False
        
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        
        if node_type == 'class_definition' or (language in ('javascript', 'typescript', 'tsx') and node_type in ('class_declaration', 'class') and node.child_count > 0):
            name_node = node.child_by_field_name('name')
            if not name_node:
                for c in node.children:
                    if c.type == 'identifier':
                        name_node = c
                        break
            class_name = get_node_text(name_node) if name_node else f"AnonymousClass_{start_line}"
            
            inherits = []
            if language == 'python':
                superclasses_node = node.child_by_field_name('superclasses')
                if superclasses_node:
                    for child in superclasses_node.children:
                        if child.type in ('identifier', 'attribute'):
                            inherits.append(get_node_text(child))
            else:
                heritage = None
                for c in node.children:
                    if c.type == 'class_heritage':
                        heritage = c
                        break
                if heritage:
                    for child in heritage.children:
                        if child.type in ('identifier', 'member_expression'):
                            inherits.append(get_node_text(child))
            
            res["classes"].append({
                "name": class_name,
                "start_line": start_line,
                "end_line": end_line,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
                "inherits": inherits,
                "text": get_node_text(node)
            })
            class_stack.append(class_name)
            pushed_class = True
            
        elif node_type == 'function_definition' or (language in ('javascript', 'typescript', 'tsx') and node_type in ('function_declaration', 'method_definition', 'arrow_function', 'generator_function_declaration') and node.child_count > 0):
            func_name = None
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = get_node_text(name_node)
            else:
                if node.parent and node.parent.type == 'variable_declarator':
                    var_name_node = node.parent.child_by_field_name('name')
                    if var_name_node:
                        func_name = get_node_text(var_name_node)
            
            if not func_name:
                func_name = f"anonymous_{start_line}"
                
            parent_class = class_stack[-1] if class_stack else None
            
            res["functions"].append({
                "name": func_name,
                "class_name": parent_class,
                "start_line": start_line,
                "end_line": end_line,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
                "text": get_node_text(node)
            })
            function_stack.append(func_name)
            pushed_func = True
            
        elif node_type in ('import_statement', 'import_from_statement'):
            if node_type == 'import_statement':
                names = []
                for c in node.children:
                    if c.type == 'dotted_name':
                        names.append(get_node_text(c))
                    elif c.type == 'aliased_name':
                        for sc in c.children:
                            if sc.type == 'dotted_name':
                                names.append(get_node_text(sc))
                res["imports"].append({
                    "module": "",
                    "names": names,
                    "start_line": start_line,
                    "end_line": end_line
                })
            else: # import_from_statement
                import_idx = -1
                for i, child in enumerate(node.children):
                    if child.type == 'import':
                        import_idx = i
                        break
                if import_idx != -1:
                    module = ""
                    module_nodes = [c for c in node.children[:import_idx] if c.type in ('dotted_name', 'relative_import')]
                    if module_nodes:
                        module = get_node_text(module_nodes[0])
                    
                    names = []
                    def collect_names(n):
                        if n.type in ('dotted_name', 'aliased_name', 'identifier'):
                            names.append(get_node_text(n))
                        elif n.type == 'import_list':
                            for sc in n.children:
                                collect_names(sc)
                    
                    for child in node.children[import_idx+1:]:
                        collect_names(child)
                    
                    res["imports"].append({
                        "module": module,
                        "names": names,
                        "start_line": start_line,
                        "end_line": end_line
                    })
                    
        elif language in ('javascript', 'typescript', 'tsx') and node_type == 'import_statement':
            module = ""
            names = []
            for c in node.children:
                if c.type == 'string':
                    module = get_node_text(c).strip('\'"')
                elif c.type == 'import_clause':
                    def collect_ids(n):
                        if n.type == 'identifier':
                            names.append(get_node_text(n))
                        for sc in n.children:
                            collect_ids(sc)
                    collect_ids(c)
            res["imports"].append({
                "module": module,
                "names": names,
                "start_line": start_line,
                "end_line": end_line
            })
            
        elif node_type == 'call' or (language in ('javascript', 'typescript', 'tsx') and node_type == 'call_expression'):
            callee_node = node.child_by_field_name('function') if language == 'python' else (node.child_by_field_name('function') or (node.children[0] if node.children else None))
            if callee_node:
                callee_text = get_node_text(callee_node).strip()
                
                caller = "global"
                if function_stack:
                    if class_stack:
                        caller = f"{class_stack[-1]}.{function_stack[-1]}"
                    else:
                        caller = function_stack[-1]
                elif class_stack:
                    caller = class_stack[-1]
                    
                res["calls"].append({
                    "caller": caller,
                    "callee": callee_text,
                    "line": start_line
                })
        
        for child in node.children:
            traverse(child)
            
        if pushed_class:
            class_stack.pop()
        if pushed_func:
            function_stack.pop()
            
    traverse(root)
    return res
