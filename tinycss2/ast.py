"""

Data structures for the CSS abstract syntax tree.

"""


from webencodings import ascii_lower

from .serializer import _serialize_to, serialize_identifier, serialize_name


class Node:
    """Every node type inherits from this class,
    which is never instantiated directly.

    .. attribute:: type

        Each child class has a :attr:`type` class attribute
        with a unique string value.
        This allows checking for the node type with code like:

        .. code-block:: python

            if node.type == 'whitespace':

        instead of the more verbose:

        .. code-block:: python

            from tinycss2.ast import WhitespaceToken
            if isinstance(node, WhitespaceToken):

    Every node also has these attributes and methods,
    which are not repeated for brevity:

    .. attribute:: source_line

        The line number of the start of the node in the CSS source.
        Starts at 1.

    .. attribute:: source_column

        The column number within :attr:`source_line` of the start of the node
        in the CSS source.
        Starts at 1.

    .. automethod:: serialize

    """
    __slots__ = ['source_line', 'source_column']

    def __init__(self, source_line, source_column):
        self.source_line = source_line
        self.source_column = source_column

    def __repr__(self):
        return self.repr_format.format(self=self)

    def serialize(self):
        """Serialize this node to CSS syntax and return a Unicode string."""
        chunks = []
        self._serialize_to(chunks.append)
        return ''.join(chunks)

    def _serialize_to(self, write):
        """Serialize this node to CSS syntax, writing chunks as Unicode string
        by calling the provided :obj:`write` callback.

        """
        raise NotImplementedError  # pragma: no cover


class ParseError(Node):
    """A syntax error of some sort. May occur anywhere in the tree.

    Syntax errors are not fatal in the parser
    to allow for different error handling behaviors.
    For example, an error in a Selector list makes the whole rule invalid,
    but an error in a Media Query list only replaces one comma-separated query
    with ``not all``.

    .. autoattribute:: type

    .. attribute:: kind

        Machine-readable string indicating the type of error.
        Example: ``'bad-url'``.

    .. attribute:: message

        Human-readable explanation of the error, as a string.
        Could be translated, expanded to include details, etc.

    """
    __slots__ = ['kind', 'message']
    type = 'error'
    repr_format = '<{self.__class__.__name__} {self.kind}>'

    def __init__(self, line, column, kind, message):
        Node.__init__(self, line, column)
        self.kind = kind
        self.message = message

    def _serialize_to(self, write):
        if self.kind == 'bad-string':
            write('"[bad string]\n')
        elif self.kind == 'bad-url':
            write('url([bad url])')
        elif self.kind in ')]}':
            write(self.kind)
        elif self.kind in ('eof-in-string', 'eof-in-url'):
            pass
        else:  # pragma: no cover
            raise TypeError('Can not serialize %r' % self)


class Comment(Node):
    """A CSS comment.

    Comments can be ignored by passing ``skip_comments=True``
    to functions such as :func:`~tinycss2.parse_component_value_list`.

    .. autoattribute:: type

    .. attribute:: value

        The content of the comment, between ``/*`` and ``*/``, as a string.

    """
    __slots__ = ['value']
    type = 'comment'
    repr_format = '<{self.__class__.__name__} {self.value}>'

    def __init__(self, line, column, value):
        Node.__init__(self, line, column)
        self.value = value

    def _serialize_to(self, write):
        write('/*')
        write(self.value)
        write('*/')


class WhitespaceToken(Node):
    """A :diagram:`whitespace-token`.

    .. autoattribute:: type

    .. attribute:: value

        The whitespace sequence, as a string, as in the original CSS source.


    """
    __slots__ = ['value']
    type = 'whitespace'
    repr_format = '<{self.__class__.__name__}>'

    def __init__(self, line, column, value):
        Node.__init__(self, line, column)
        self.value = value

    def _serialize_to(self, write):
        write(self.value)


class LiteralToken(Node):
    r"""Token that represents one or more characters as in the CSS source.

    .. autoattribute:: type

    .. attribute:: value

        A string of one to four characters.

    Instances compare equal to their :attr:`value`,
    so that these are equivalent:

    .. code-block:: python

        if node == ';':
        if node.type == 'literal' and node.value == ';':

    This regroups what `the specification`_ defines as separate token types:

    .. _the specification: https://drafts.csswg.org/css-syntax-3/

    * *<colon-token>* ``:``
    * *<semicolon-token>* ``;``
    * *<comma-token>* ``,``
    * *<cdc-token>* ``-->``
    * *<cdo-token>* ``<!--``
    * *<include-match-token>* ``~=``
    * *<dash-match-token>* ``|=``
    * *<prefix-match-token>* ``^=``
    * *<suffix-match-token>* ``$=``
    * *<substring-match-token>* ``*=``
    * *<column-token>* ``||``
    * *<delim-token>* (a single ASCII character not part of any another token)

    """
    __slots__ = ['value']
    type = 'literal'
    repr_format = '<{self.__class__.__name__} {self.value}>'

    def __init__(self, line, column, value):
        Node.__init__(self, line, column)
        self.value = value

    def __eq__(self, other):
        return self.value == other or self is other

    def __ne__(self, other):
        return not self == other

    def _serialize_to(self, write):
        write(self.value)


class IdentToken(Node):
    """An :diagram:`ident-token`.

    .. autoattribute:: type

    .. attribute:: value

        The unescaped value, as a Unicode string.

    .. attribute:: lower_value

        Same as :attr:`value` but normalized to *ASCII lower case*,
        see :func:`~webencodings.ascii_lower`.
        This is the value to use when comparing to a CSS keyword.

    """
    __slots__ = ['value', 'lower_value']
    type = 'ident'
    repr_format = '<{self.__class__.__name__} {self.value}>'

    def __init__(self, line, column, value):
        Node.__init__(self, line, column)
        self.value = value
        try:
            self.lower_value = ascii_lower(value)
        except UnicodeEncodeError:
            self.lower_value = value

    def _serialize_to(self, write):
        write(serialize_identifier(self.value))


class AtKeywordToken(Node):
    """An :diagram:`at-keyword-token`.

    .. code-block:: text

        '@' <value>

    .. autoattribute:: type

    .. attribute:: value

        The unescaped value, as a Unicode string, without the preceding ``@``.

    .. attribute:: lower_value

        Same as :attr:`value` but normalized to *ASCII lower case*,
        see :func:`~webencodings.ascii_lower`.
        This is the value to use when comparing to a CSS at-keyword.

        .. code-block:: python

            if node.type == 'at-keyword' and node.lower_value == 'import':

    """
    __slots__ = ['value', 'lower_value']
    type = 'at-keyword'
    repr_format = '<{self.__class__.__name__} @{self.value}>'

    def __init__(self, line, column, value):
        Node.__init__(self, line, column)
        self.value = value
        try:
            self.lower_value = ascii_lower(value)
        except UnicodeEncodeError:
            self.lower_value = value

    def _serialize_to(self, write):
        write('@')
        write(serialize_identifier(self.value))


class HashToken(Node):
    r"""A :diagram:`hash-token`.

    .. code-block:: text

        '#' <value>

    .. autoattribute:: type

    .. attribute:: value

        The unescaped value, as a Unicode string, without the preceding ``#``.

    .. attribute:: is_identifier

        A boolean, true if the CSS source for this token
        was ``#`` followed by a valid identifier.
        (Only such hash tokens are valid ID selectors.)

    """
    __slots__ = ['value', 'is_identifier']
    type = 'hash'
    repr_format = '<{self.__class__.__name__} #{self.value}>'

    def __init__(self, line, column, value, is_identifier):
        Node.__init__(self, line, column)
        self.value = value
        self.is_identifier = is_identifier

    def _serialize_to(self, write):
        write('#')
        if self.is_identifier:
            write(serialize_identifier(self.value))
        else:
            write(serialize_name(self.value))


class StringToken(Node):
    """A :diagram:`string-token`.

    .. code-block:: text

        '"' <value> '"'

    .. autoattribute:: type

    .. attribute:: value

        The unescaped value, as a Unicode string, without the quotes.

    """
    __slots__ = ['value', 'representation']
    type = 'string'
    repr_format = '<{self.__class__.__name__} {self.representation}>'

    def __init__(self, line, column, value, representation):
        Node.__init__(self, line, column)
        self.value = value
        self.representation = representation

    def _serialize_to(self, write):
        write(self.representation)


class URLToken(Node):
    """An :diagram:`url-token`.

    .. code-block:: text

        'url(' <value> ')'

    .. autoattribute:: type

    .. attribute:: value

        The unescaped URL, as a Unicode string, without the ``url(`` and ``)``
        markers.

    """
    __slots__ = ['value', 'representation']
    type = 'url'
    repr_format = '<{self.__class__.__name__} {self.representation}>'

    def __init__(self, line, column, value, representation):
        Node.__init__(self, line, column)
        self.value = value
        self.representation = representation

    def _serialize_to(self, write):
        write(self.representation)


class UnicodeRangeToken(Node):
    """A `unicode-range token <https://www.w3.org/TR/css-syntax-3/#urange>`_.

    .. autoattribute:: type

    .. attribute:: start

        The start of the range, as an integer between 0 and 1114111.

    .. attribute:: end

        The end of the range, as an integer between 0 and 1114111.
        Same as :attr:`start` if the source only specified one value.

    """
    __slots__ = ['start', 'end']
    type = 'unicode-range'
    repr_format = '<{self.__class__.__name__} {self.start} {self.end}>'

    def __init__(self, line, column, start, end):
        Node.__init__(self, line, column)
        self.start = start
        self.end = end

    def _serialize_to(self, write):
        if self.end == self.start:
            write('U+%X' % self.start)
        else:
            write('U+%X-%X' % (self.start, self.end))


class NumberToken(Node):
    """A :diagram:`number-token`.

    .. autoattribute:: type

    .. attribute:: value

        The numeric value as a :class:`float`.

    .. attribute:: int_value

        The numeric value as an :class:`int`
        if :attr:`is_integer` is true, :obj:`None` otherwise.

    .. attribute:: is_integer

        Whether the token was syntactically an integer, as a boolean.

    .. attribute:: representation

        The CSS representation of the value, as a Unicode string.

    """
    __slots__ = ['value', 'int_value', 'is_integer', 'representation']
    type = 'number'
    repr_format = '<{self.__class__.__name__} {self.representation}>'

    def __init__(self, line, column, value, int_value, representation):
        Node.__init__(self, line, column)
        self.value = value
        self.int_value = int_value
        self.is_integer = int_value is not None
        self.representation = representation

    def _serialize_to(self, write):
        write(self.representation)


class PercentageToken(Node):
    """A :diagram:`percentage-token`.

    .. code-block:: text

        <representation> '%'

    .. autoattribute:: type

    .. attribute:: value

        The value numeric as a :class:`float`.

    .. attribute:: int_value

        The numeric value as an :class:`int`
        if the token was syntactically an integer,
        or :obj:`None`.

    .. attribute:: is_integer

        Whether the token’s value was syntactically an integer, as a boolean.

    .. attribute:: representation

        The CSS representation of the value without the unit,
        as a Unicode string.

    """
    __slots__ = ['value', 'int_value', 'is_integer', 'representation']
    type = 'percentage'
    repr_format = '<{self.__class__.__name__} {self.representation}%>'

    def __init__(self, line, column, value, int_value, representation):
        Node.__init__(self, line, column)
        self.value = value
        self.int_value = int_value
        self.is_integer = int_value is not None
        self.representation = representation

    def _serialize_to(self, write):
        write(self.representation)
        write('%')


class DimensionToken(Node):
    """A :diagram:`dimension-token`.

    .. code-block:: text

        <representation> <unit>

    .. autoattribute:: type

    .. attribute:: value

        The value numeric as a :class:`float`.

    .. attribute:: int_value

        The numeric value as an :class:`int`
        if the token was syntactically an integer,
        or :obj:`None`.

    .. attribute:: is_integer

        Whether the token’s value was syntactically an integer, as a boolean.

    .. attribute:: representation

        The CSS representation of the value without the unit,
        as a Unicode string.

    .. attribute:: unit

        The unescaped unit, as a Unicode string.

    .. attribute:: lower_unit

        Same as :attr:`unit` but normalized to *ASCII lower case*,
        see :func:`~webencodings.ascii_lower`.
        This is the value to use when comparing to a CSS unit.

        .. code-block:: python

            if node.type == 'dimension' and node.lower_unit == 'px':

    """
    __slots__ = ['value', 'int_value', 'is_integer', 'representation',
                 'unit', 'lower_unit']
    type = 'dimension'
    repr_format = ('<{self.__class__.__name__} '
                   '{self.representation}{self.unit}>')

    def __init__(self, line, column, value, int_value, representation, unit):
        Node.__init__(self, line, column)
        self.value = value
        self.int_value = int_value
        self.is_integer = int_value is not None
        self.representation = representation
        self.unit = unit
        self.lower_unit = ascii_lower(unit)

    def _serialize_to(self, write):
        write(self.representation)
        # Disambiguate with scientific notation
        unit = self.unit
        if unit in ('e', 'E') or unit.startswith(('e-', 'E-')):
            write('\\65 ')
            write(serialize_name(unit[1:]))
        else:
            write(serialize_identifier(unit))


class ParenthesesBlock(Node):
    """A :diagram:`()-block`.

    .. code-block:: text

        '(' <content> ')'

    .. autoattribute:: type

    .. attribute:: content

        The content of the block, as list of :term:`component values`.
        The ``(`` and ``)`` markers themselves are not represented in the list.

    """
    __slots__ = ['content']
    type = '() block'
    repr_format = '<{self.__class__.__name__} ( … )>'

    def __init__(self, line, column, content):
        Node.__init__(self, line, column)
        self.content = content

    def _serialize_to(self, write):
        write('(')
        _serialize_to(self.content, write)
        write(')')


class SquareBracketsBlock(Node):
    """A :diagram:`[]-block`.

    .. code-block:: text

        '[' <content> ']'

    .. autoattribute:: type

    .. attribute:: content

        The content of the block, as list of :term:`component values`.
        The ``[`` and ``]`` markers themselves are not represented in the list.

    """
    __slots__ = ['content']
    type = '[] block'
    repr_format = '<{self.__class__.__name__} [ … ]>'

    def __init__(self, line, column, content):
        Node.__init__(self, line, column)
        self.content = content

    def _serialize_to(self, write):
        write('[')
        _serialize_to(self.content, write)
        write(']')


class CurlyBracketsBlock(Node):
    """A :diagram:`{}-block`.

    .. code-block:: text

        '{' <content> '}'

    .. autoattribute:: type

    .. attribute:: content

        The content of the block, as list of :term:`component values`.
        The ``[`` and ``]`` markers themselves are not represented in the list.

    """
    __slots__ = ['content']
    type = '{} block'
    repr_format = '<{self.__class__.__name__} {{ … }}>'

    def __init__(self, line, column, content):
        Node.__init__(self, line, column)
        self.content = content

    def _serialize_to(self, write):
        write('{')
        _serialize_to(self.content, write)
        write('}')


class FunctionBlock(Node):
    """A :diagram:`function-block`.

    .. code-block:: text

        <name> '(' <arguments> ')'

    .. autoattribute:: type

    .. attribute:: name

        The unescaped name of the function, as a Unicode string.

    .. attribute:: lower_name

        Same as :attr:`name` but normalized to *ASCII lower case*,
        see :func:`~webencodings.ascii_lower`.
        This is the value to use when comparing to a CSS function name.

    .. attribute:: arguments

        The arguments of the function, as list of :term:`component values`.
        The ``(`` and ``)`` markers themselves are not represented in the list.
        Commas are not special, but represented as :obj:`LiteralToken` objects
        in the list.

    """
    __slots__ = ['name', 'lower_name', 'arguments']
    type = 'function'
    repr_format = '<{self.__class__.__name__} {self.name}( … )>'

    def __init__(self, line, column, name, arguments):
        Node.__init__(self, line, column)
        self.name = name
        self.lower_name = ascii_lower(name)
        self.arguments = arguments

    def _serialize_to(self, write):
        write(serialize_identifier(self.name))
        write('(')
        _serialize_to(self.arguments, write)
        if self.arguments:
            function = self
            while isinstance(function, FunctionBlock):
                eof_in_string = (
                    isinstance(function.arguments[-1], ParseError) and
                    function.arguments[-1].kind == 'eof-in-string')
                if eof_in_string:
                    return
                function = function.arguments[-1]
        write(')')


class Declaration(Node):
    """A (property or descriptor) :diagram:`declaration`.

    .. code-block:: text

        <name> ':' <value>
        <name> ':' <value> '!important'

    .. autoattribute:: type

    .. attribute:: name

        The unescaped name, as a Unicode string.

    .. attribute:: lower_name

        Same as :attr:`name` but normalized to *ASCII lower case*,
        see :func:`~webencodings.ascii_lower`.
        This is the value to use when comparing to
        a CSS property or descriptor name.

        .. code-block:: python

            if node.type == 'declaration' and node.lower_name == 'color':

    .. attribute:: value

        The declaration value as a list of :term:`component values`:
        anything between ``:`` and
        the end of the declaration, or ``!important``.

    .. attribute:: important

        A boolean, true if the declaration had an ``!important`` marker.
        It is up to the consumer to reject declarations that do not accept
        this flag, such as non-property descriptor declarations.

    """
    __slots__ = ['name', 'lower_name', 'value', 'important']
    type = 'declaration'
    repr_format = '<{self.__class__.__name__} {self.name}: …>'

    def __init__(self, line, column, name, lower_name, value, important):
        Node.__init__(self, line, column)
        self.name = name
        self.lower_name = lower_name
        self.value = value
        self.important = important

    def _serialize_to(self, write):
        write(serialize_identifier(self.name))
        write(':')
        _serialize_to(self.value, write)
        if self.important:
            write('!important')


class QualifiedRule(Node):
    """A :diagram:`qualified rule`.

    .. code-block:: text

        <prelude> '{' <content> '}'

    The interpretation of qualified rules depend on their context.
    At the top-level of a stylesheet
    or in a conditional rule such as ``@media``,
    they are **style rules** where the :attr:`prelude` is Selectors list
    and the :attr:`content` is a list of property declarations.

    .. autoattribute:: type

    .. attribute:: prelude

        The rule’s prelude, the part before the {} block,
        as a list of :term:`component values`.

    .. attribute:: content

        The rule’s content, the part inside the {} block,
        as a list of :term:`component values`.

    """
    __slots__ = ['prelude', 'content']
    type = 'qualified-rule'
    repr_format = ('<{self.__class__.__name__} '
                   '… {{ … }}>')

    def __init__(self, line, column, prelude, content):
        Node.__init__(self, line, column)
        self.prelude = prelude
        self.content = content

    def _serialize_to(self, write):
        _serialize_to(self.prelude, write)
        write('{')
        _serialize_to(self.content, write)
        write('}')


class AtRule(Node):
    """An :diagram:`at-rule`.

    .. code-block:: text

        @<at_keyword> <prelude> '{' <content> '}'
        @<at_keyword> <prelude> ';'

    The interpretation of at-rules depend on their at-keyword
    as well as their context.
    Most types of at-rules (ie. at-keyword values)
    are only allowed in some context,
    and must either end with a {} block or a semicolon.

    .. autoattribute:: type

    .. attribute:: at_keyword

        The unescaped value of the rule’s at-keyword,
        without the ``@`` symbol, as a Unicode string.

    .. attribute:: lower_at_keyword

        Same as :attr:`at_keyword` but normalized to *ASCII lower case*,
        see :func:`~webencodings.ascii_lower`.
        This is the value to use when comparing to a CSS at-keyword.

        .. code-block:: python

            if node.type == 'at-rule' and node.lower_at_keyword == 'import':

    .. attribute:: prelude

        The rule’s prelude, the part before the {} block or semicolon,
        as a list of :term:`component values`.

    .. attribute:: content

        The rule’s content, if any.
        The block’s content as a list of :term:`component values`
        for at-rules with a {} block,
        or :obj:`None` for at-rules ending with a semicolon.

    """
    __slots__ = ['at_keyword', 'lower_at_keyword', 'prelude', 'content']
    type = 'at-rule'
    repr_format = ('<{self.__class__.__name__} '
                   '@{self.at_keyword} … {{ … }}>')

    def __init__(self, line, column,
                 at_keyword, lower_at_keyword, prelude, content):
        Node.__init__(self, line, column)
        self.at_keyword = at_keyword
        self.lower_at_keyword = lower_at_keyword
        self.prelude = prelude
        self.content = content

    def _serialize_to(self, write):
        write('@')
        write(serialize_identifier(self.at_keyword))
        _serialize_to(self.prelude, write)
        if self.content is None:
            write(';')
        else:
            write('{')
            _serialize_to(self.content, write)
            write('}')
