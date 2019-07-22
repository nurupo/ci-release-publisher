# -*- coding: utf-8 -*-

def enum_to_arg_choices(enum_calss):
    return [e.name.lower().replace('_', '-') for e in enum_calss]

def arg_choices_to_enum(enum_calss, choices):
    return [enum_calss[s.upper().replace('-', '_')] for s in choices]
