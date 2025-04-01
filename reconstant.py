from typing import Dict, List, TextIO, Union
import argparse
import os
import textwrap
import yaml


class Enum:
    name: str
    values: List[str]

    def __init__(self, name, values):
        self.name = name
        self.values = values


class Operation:
    operationType: str
    operands: List

    def __init__(self, operands, operationType):
        self.operands = operands
        self.operationType = operationType

    def output(self, prefix, symbol, suffix, stringDelimiter='"'):
        output = prefix
        separator = ''
        for operand in self.operands:
            if Constant.INDEX_VALUE in operand:
                if self.operationType == Constant.INDEX_OPERATION_CONCAT:
                    output = output + separator + f'{stringDelimiter}{operand[Constant.INDEX_VALUE]}{stringDelimiter}'
                else:
                    output = output + separator + f"{operand[Constant.INDEX_VALUE]}"
            elif Constant.INDEX_REFERENCE in operand:
                output = output + separator + operand[Constant.INDEX_REFERENCE]
            separator = symbol
        output = output + suffix

        return output


class Constant:
    # Indexes
    INDEX_VALUE = 'value'
    INDEX_REFERENCE = 'ref'
    INDEX_OPERATION_CONCAT = 'concat'
    INDEX_OPERATION_SUM = 'sum'
    INDEX_OPERATION_SUB = 'sub'
    INDEX_OPERATION_MUL = 'mul'
    INDEX_OPERATION_DIV = 'div'

    name: str
    value: str
    constantType: type
    operation: Operation

    def __init__(self, constantDefinition):
        self.name = constantDefinition['name']
        self.value = None
        self.operation = None
        if Constant.INDEX_VALUE in constantDefinition:
            self.value = constantDefinition[Constant.INDEX_VALUE]
            self.constantType = type(self.value)
        else:
            if Constant.INDEX_OPERATION_CONCAT in constantDefinition:
                self.operation = Operation(constantDefinition[Constant.INDEX_OPERATION_CONCAT], Constant.INDEX_OPERATION_CONCAT)
            elif Constant.INDEX_OPERATION_SUM in constantDefinition:
                self.operation = Operation(constantDefinition[Constant.INDEX_OPERATION_SUM], Constant.INDEX_OPERATION_SUM)
            elif Constant.INDEX_OPERATION_SUB in constantDefinition:
                self.operation = Operation(constantDefinition[Constant.INDEX_OPERATION_SUB], Constant.INDEX_OPERATION_SUB)
            elif Constant.INDEX_OPERATION_MUL in constantDefinition:
                self.operation = Operation(constantDefinition[Constant.INDEX_OPERATION_MUL], Constant.INDEX_OPERATION_MUL)
            elif Constant.INDEX_OPERATION_DIV in constantDefinition:
                self.operation = Operation(constantDefinition[Constant.INDEX_OPERATION_DIV], Constant.INDEX_OPERATION_DIV)

            for operand in self.operation.operands:
                if Constant.INDEX_VALUE in operand:
                    self.constantType = type(operand[Constant.INDEX_VALUE])


class Outputer:
    path: str
    _output: TextIO
    _comment_mark: str
    _comment_indentation: int  # doesn't apply to the comment in output_header()
    _concat_marks: List[str]
    _addition_marks: List[str]
    _substraction_marks: List[str]
    _multiplier_marks: List[str]
    _divider_marks: List[str]
    _hasEnums: bool = False
    _hasConstants: bool = False

    def __init__(self, *args, **kwargs):
        self.path = args[0]['path']
        self._output = open(self.path, "w+")
        self._comment_mark = '//'
        self._comment_indentation = 0
        self._string_delimiter = '"'
        self._concat_marks = ['', ' + ', '']
        self._addition_marks = ['', ' + ', '']
        self._substraction_marks = ['', ' - ', '']
        self._multiplier_marks = ['', ' * ', '']
        self._divider_marks = ['', ' / ', '']

    def __del__(self):
        self._output.close()

    def output_enum(self, enum: Enum, prefix="", assignment="=", suffix=""):
        for (i, value) in enumerate(enum.values):
            self._output.write(f"{prefix}{value} {assignment} {i}{suffix}\n")

    def output_comment(self, comment):
        indent = '\t' * self._comment_indentation
        self._output.write(f"\n{indent}{self._comment_mark} {comment}\n")

    def output_constant(self, constant: Constant, prefix="", assignment=" = ", suffix=""):
        if constant.value is not None:
            if constant.constantType == int:
                value = constant.value
            elif constant.constantType == str:
                value = f'{self._string_delimiter}{constant.value}{self._string_delimiter}'
            else:
                raise Exception("Internal error - illegal constant type. %s", constant.constantType)
            self._output.write(f"{prefix}{constant.name}{assignment}{value}{suffix}\n")
        elif constant.operation is not None:
            constantOutput = ''
            match constant.operation.operationType:
                case Constant.INDEX_OPERATION_CONCAT:
                    constantOutput = constant.operation.output(*self._concat_marks, self._string_delimiter)
                case Constant.INDEX_OPERATION_SUM:
                    constantOutput = constant.operation.output(*self._addition_marks)
                case Constant.INDEX_OPERATION_SUB:
                    constantOutput = constant.operation.output(*self._substraction_marks)
                case Constant.INDEX_OPERATION_MUL:
                    constantOutput = constant.operation.output(*self._multiplier_marks)
                case Constant.INDEX_OPERATION_DIV:
                    constantOutput = constant.operation.output(*self._divider_marks)

            self._output.write(f"{prefix}{constant.name}{assignment}{constantOutput}{suffix}\n")

    def output_header(self):
        self._output.write(f"{self._comment_mark} autogenerated by reconstant - do not edit!\n")

    def output_footer(self):
        pass

    def setHasEnum(self, hasEnum: bool):
        self._hasEnums = hasEnum

    def setHasConstants(self, hasConstants: bool):
        self._hasConstants = hasConstants


class PythonOutputer (Outputer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._comment_mark = '#'
        self._string_delimiter = "'"

    def output_header(self):
        super().output_header()
        if self._hasEnums:
            self._output.write("from enum import Enum\n")

    def output_enum(self, enum: Enum):
        self._output.write(f"class {enum.name}(Enum):\n")
        super().output_enum(enum, prefix=f"\t")
        self._output.write(f"\n")


class JavascriptOutputer (Outputer):
    def output_enum(self, enum: Enum):
        self._output.write(f"export const {enum.name} = {{\n")
        super().output_enum(enum, prefix=f"\t", assignment=":", suffix=",")
        self._string_delimiter = "'"
        self._output.write(f"}}\n")

    def output_constant(self, constant: Constant):
        return super().output_constant(constant, prefix="export const ")


class PhpOutputer (Outputer):
    _namespaceDefinition: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._concat_marks = ['', '.', '']
        self._string_delimiter = "'"
        self._namespaceDefinition = args[0]['namespace']

    def output_header(self):
        self._output.write("<?php\n")
        super().output_header()
        if self._namespaceDefinition:
            self._output.write(f'namespace {self._namespaceDefinition};\n')

    def output_enum(self, enum: Enum):
        separator = ';\n\tcase '
        self._output.write(f"enum {enum.name} {{\n\tcase {separator.join([val for val in enum.values])};\n}}\n")

    def output_constant(self, constant: Constant):
        return super().output_constant(constant, prefix="Define('", assignment="', ", suffix=");")


class JavaOutputer (Outputer):
    _packageDefinition: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._comment_indentation = 1
        self._packageDefinition = args[0]['package']

    def output_header(self):
        super().output_header()
        if self._packageDefinition:
            self._output.write(f'package {self._packageDefinition};\n\n')

        class_name = self._get_class_name()
        self._output.write(textwrap.dedent(f"""\
            public final class {class_name} {{
            """))

    def output_footer(self):
        super().output_footer()
        self._output.write("\n}")

    def _get_class_name(self):
        return os.path.basename(self.path).replace(".java", "")

    def output_enum(self, enum: Enum):
        separator = ', \n\t\t'
        self._output.write(f"\tpublic enum {enum.name} {{\n\t\t{separator.join([val for val in enum.values])}\n\t}}\n")

    def output_constant(self, constant: Constant):
        constantType = 'String' if constant.constantType == str else constant.constantType.__name__
        return super().output_constant(constant, prefix=f"\tpublic static final {constantType} ", suffix=";")


class RustOutputer (Outputer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._concat_marks = ['concatcp!(', ',', ')']

    def output_header(self):
        super().output_header()
        if self._hasConstants:
            self._output.write("use const_format::concatcp;\n")

    def output_enum(self, enum: Enum):
        separator = ', \n\t'
        self._output.write(f"pub enum {enum.name} {{\n\t{separator.join([val for val in enum.values])}\n}}\n")

    def output_constant(self, constant: Constant):
        t = {int: 'i32', float: 'f32', str: '&str'}.get(constant.constantType, constant.constantType.__name__)
        quotes = '"' if t == '&str' else ''
        return super().output_constant(constant, prefix=f"pub const ", assignment=f': {t} = ', suffix=";")


class COutputer (Outputer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._concat_marks = ['', ' ', '']

    def output_header(self):
        super().output_header()
        guard_name = self._get_guard_name()
        self._output.write(textwrap.dedent(f"""\
            #ifndef {guard_name}
            #define {guard_name}
            """))

    def output_footer(self):
        super().output_footer()
        guard_name = self._get_guard_name()
        self._output.write(f"\n#endif /* {guard_name} */")

    def _get_guard_name(self):
        return self.path.replace('/', '_').replace(".", "_").upper()

    def output_enum(self, enum: Enum):
        self._output.write(f"typedef enum {{ {', '.join([val for val in enum.values])} }} {enum.name};\n")

    def output_constant(self, constant: Constant):
        return super().output_constant(constant, prefix=f"#define ", suffix="")


# idea from https://stackoverflow.com/a/65734013/495995
class VueMixinOutputer (JavascriptOutputer):
    def output_enum(self, enum: Enum):
        super().output_enum(enum)
        name = enum.name
        self._output.write(textwrap.dedent(f"""\
            
            {name}.Mixin = {{
              created () {{
                  this.{name} = {name}
              }}
            }}
            """))

class ROutputer (Outputer):
    """R-language Outputer"""

    def __init__(self, *args, **kwargs):
        super().__init__(comment_mark="#", *args, **kwargs)

    def output_enum(self, constant : Constant):
        constant.name = ''.join(['_' + l if l.isupper() else l.upper() for l in constant.name]).strip('_')
        super().output_enum(constant, assignment=" <- ", prefix=f"{constant.name}_")

    def output_constant(self, constant: Constant, prefix="", suffix=""):
        return super().output_constant(constant, assignment=" <- ", suffix="")


class DartOutputer (Outputer):
    """Dart-language Outputer"""

    def __init__(self, *args, **kwargs):
        super().__init__(comment_mark="//", *args, **kwargs)

    def output_header(self):
        super().output_header()
        self._output.write("library constants;\n\n")

    def output_enum(self, enum: Enum):
        # Convert enum values to lowercase for more Dart-like style
        separator = ',\n\tcase '
        self._output.write(f"enum {enum.name} {{\n\t{separator.join([val.lower() for val in enum.values])},\n}}\n")


class RootConfig:
    enums: List[Enum] = []
    constants: List[Constant] = []
    outputs: Dict[str, Outputer] = {}

    def __init__(self, rawObject):
        if 'enums' in rawObject:
            self.readEnums(rawObject['enums'])
        if 'constants' in rawObject:
            self.readConstants(rawObject['constants'])
        self.readOutputers(rawObject['outputs'])

    def readEnums(self, enumList: Dict):
        for enum in enumList:
            self.enums.append(Enum(enum['name'], enum['values']))

    def readConstants(self, constantsList: Dict):
        for constant in constantsList:
            self.constants.append(Constant(constant))

    def readOutputers(self, outputerList: Dict):
        for key in outputerList:
            match key:
                case 'c':
                    self.outputs[key] = COutputer(outputerList[key])
                case 'dart':
                    self.outputs[key] = DartOutputer(outputerList[key])
                case 'java':
                    self.outputs[key] = JavaOutputer(outputerList[key])
                case 'javascript':
                    self.outputs[key] = JavascriptOutputer(outputerList[key])
                case 'php':
                    self.outputs[key] = PhpOutputer(outputerList[key])
                case 'python':
                    self.outputs[key] = PythonOutputer(outputerList[key])
                case 'r':
                    self.outputs[key] = ROutputer(outputerList[key])
                case 'rust':
                    self.outputs[key] = RustOutputer(outputerList[key])
                case 'vue':
                    self.outputs[key] = VueMixinOutputer(outputerList[key])
                case _:
                    raise NotImplementedError(f"{key} is not a supported constant langage")

            self.outputs[key].setHasEnum(len(self.enums) > 0)
            self.outputs[key].setHasConstants(len(self.constants) > 0)


def process_input(config: RootConfig):
    for language in config.outputs:
        outputer = config.outputs[language]
        outputer.output_header()
        outputer.output_comment("constants")
        for constant in config.constants:
            outputer.output_constant(constant)
        outputer.output_comment("enums")
        for enum in config.enums:
            outputer.output_enum(enum)
        outputer.output_footer()


def main():
    parser = argparse.ArgumentParser(
        description='Reconstant - Share constant definitions between programming languages and make your constants constant again.')
    parser.add_argument('input', type=str, help='input file in yaml format')
    args = parser.parse_args()

    with open(args.input, "r") as yaml_input:
        python_obj = yaml.safe_load(yaml_input)
        config = RootConfig(python_obj)
        process_input(config)


if __name__ == "__main__":
    main()
