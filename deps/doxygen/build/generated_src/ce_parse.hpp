/* A Bison parser, made by GNU Bison 3.8.2.  */

/* Bison interface for Yacc-like parsers in C

   Copyright (C) 1984, 1989-1990, 2000-2015, 2018-2021 Free Software Foundation,
   Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.  */

/* As a special exception, you may create a larger work that contains
   part or all of the Bison parser skeleton and distribute that work
   under terms of your choice, so long as that work isn't itself a
   parser generator using the skeleton or a modified version thereof
   as a parser skeleton.  Alternatively, if you modify or redistribute
   the parser skeleton itself, you may (at your option) remove this
   special exception, which will cause the skeleton and the resulting
   Bison output files to be licensed under the GNU General Public
   License without this special exception.

   This special exception was added by the Free Software Foundation in
   version 2.2 of Bison.  */

/* DO NOT RELY ON FEATURES THAT ARE NOT DOCUMENTED in the manual,
   especially those whose name start with YY_ or yy_.  They are
   private implementation details that can be changed or removed.  */

#ifndef YY_CONSTEXPYY_HOME_RUNNER_WORK_ADCAM_ADCAM_DEPS_DOXYGEN_BUILD_GENERATED_SRC_CE_PARSE_HPP_INCLUDED
# define YY_CONSTEXPYY_HOME_RUNNER_WORK_ADCAM_ADCAM_DEPS_DOXYGEN_BUILD_GENERATED_SRC_CE_PARSE_HPP_INCLUDED
/* Debug traces.  */
#ifndef YYDEBUG
# define YYDEBUG 0
#endif
#if YYDEBUG
extern int constexpYYdebug;
#endif

/* Token kinds.  */
#ifndef YYTOKENTYPE
# define YYTOKENTYPE
  enum yytokentype
  {
    YYEMPTY = -2,
    YYEOF = 0,                     /* "end of file"  */
    YYerror = 256,                 /* error  */
    YYUNDEF = 257,                 /* "invalid token"  */
    TOK_QUESTIONMARK = 258,        /* TOK_QUESTIONMARK  */
    TOK_COLON = 259,               /* TOK_COLON  */
    TOK_OR = 260,                  /* TOK_OR  */
    TOK_AND = 261,                 /* TOK_AND  */
    TOK_BITWISEOR = 262,           /* TOK_BITWISEOR  */
    TOK_BITWISEXOR = 263,          /* TOK_BITWISEXOR  */
    TOK_AMPERSAND = 264,           /* TOK_AMPERSAND  */
    TOK_NOTEQUAL = 265,            /* TOK_NOTEQUAL  */
    TOK_EQUAL = 266,               /* TOK_EQUAL  */
    TOK_LESSTHAN = 267,            /* TOK_LESSTHAN  */
    TOK_GREATERTHAN = 268,         /* TOK_GREATERTHAN  */
    TOK_LESSTHANOREQUALTO = 269,   /* TOK_LESSTHANOREQUALTO  */
    TOK_GREATERTHANOREQUALTO = 270, /* TOK_GREATERTHANOREQUALTO  */
    TOK_SHIFTLEFT = 271,           /* TOK_SHIFTLEFT  */
    TOK_SHIFTRIGHT = 272,          /* TOK_SHIFTRIGHT  */
    TOK_PLUS = 273,                /* TOK_PLUS  */
    TOK_MINUS = 274,               /* TOK_MINUS  */
    TOK_STAR = 275,                /* TOK_STAR  */
    TOK_DIVIDE = 276,              /* TOK_DIVIDE  */
    TOK_MOD = 277,                 /* TOK_MOD  */
    TOK_TILDE = 278,               /* TOK_TILDE  */
    TOK_NOT = 279,                 /* TOK_NOT  */
    TOK_LPAREN = 280,              /* TOK_LPAREN  */
    TOK_RPAREN = 281,              /* TOK_RPAREN  */
    TOK_OCTALINT = 282,            /* TOK_OCTALINT  */
    TOK_DECIMALINT = 283,          /* TOK_DECIMALINT  */
    TOK_HEXADECIMALINT = 284,      /* TOK_HEXADECIMALINT  */
    TOK_CHARACTER = 285,           /* TOK_CHARACTER  */
    TOK_FLOAT = 286                /* TOK_FLOAT  */
  };
  typedef enum yytokentype yytoken_kind_t;
#endif

/* Value type.  */
#if ! defined YYSTYPE && ! defined YYSTYPE_IS_DECLARED
typedef int YYSTYPE;
# define YYSTYPE_IS_TRIVIAL 1
# define YYSTYPE_IS_DECLARED 1
#endif


extern YYSTYPE constexpYYlval;


int constexpYYparse (void);


#endif /* !YY_CONSTEXPYY_HOME_RUNNER_WORK_ADCAM_ADCAM_DEPS_DOXYGEN_BUILD_GENERATED_SRC_CE_PARSE_HPP_INCLUDED  */
