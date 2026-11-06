IF_KINDS = frozenset({"if_statement", "if_expression", "if", "unless"})

ELSE_CONTAINERS = frozenset({"else_clause", "else"})

CONTROL_KINDS = frozenset(
    {
        "for_statement",
        "for_in_statement",
        "for_of_statement",
        "for_expression",
        "for_range_loop",
        "enhanced_for_statement",
        "foreach_statement",
        "while_statement",
        "while_expression",
        "do_statement",
        "loop_expression",
        "try_statement",
        "try_expression",
        "with_statement",
        "using_statement",
        "lock_statement",
        "match_statement",
        "match_expression",
        "switch_statement",
        "switch_expression",
        "expression_switch_statement",
        "type_switch_statement",
        "select_statement",
        "case_statement",
        "while",
        "until",
        "for",
        "case",
        "begin",
    }
)

ANONYMOUS_FUNCTION_KINDS = frozenset(
    {
        "lambda",
        "lambda_expression",
        "arrow_function",
        "function_expression",
        "func_literal",
        "closure_expression",
        "anonymous_function",
    }
)

COMPREHENSION_KINDS = frozenset(
    {"list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression"}
)

LEVEL_KINDS = IF_KINDS | CONTROL_KINDS | ANONYMOUS_FUNCTION_KINDS | COMPREHENSION_KINDS

NAMED_FUNCTION_KINDS = frozenset(
    {
        "function_definition",
        "function_declaration",
        "generator_function_declaration",
        "function_item",
        "method_definition",
        "method_declaration",
        "constructor_declaration",
        "method",
        "singleton_method",
    }
)

FUNCTION_KINDS = NAMED_FUNCTION_KINDS | ANONYMOUS_FUNCTION_KINDS

NESTED_SCOPE_KINDS = FUNCTION_KINDS | {"class_definition"}

ASYNC_KINDS = frozenset({"function_definition", "for_statement", "with_statement"})

CALL_KINDS = frozenset({"call", "call_expression"})

COMMENT_KINDS = frozenset({"comment", "line_comment", "block_comment"})

DOCUMENTATION_PREFIXES = ("///", "//!", "/**", "/*!")

DOCSTRING_CONTAINERS = frozenset({"module", "block"})

DOCSTRING_LANGUAGES = frozenset({"python"})

NAME_BINDING_KINDS = frozenset(
    {
        "variable_declarator",
        "assignment",
        "assignment_expression",
        "pair",
        "public_field_definition",
        "field_definition",
        "let_declaration",
        "short_var_declaration",
    }
)
