/**
 * ADR-274 D4: Safe expression evaluator for computed stats and color rules.
 *
 * Custom recursive-descent parser — no third-party expression library.
 * Only whitelisted aggregate functions and arithmetic operators are available.
 * No eval(), Function(), or prototype access — immune to code injection.
 */

// ── Types ────────────────────────────────────────────────────────────

type TokenType =
  | 'number'
  | 'string'
  | 'ident'
  | '+'
  | '-'
  | '*'
  | '/'
  | '%'
  | '**'
  | '('
  | ')'
  | ','
  | '?'
  | ':'
  | '<'
  | '>'
  | '<='
  | '>='
  | '=='
  | '!='
  | '&&'
  | '||'
  | '!'
  | 'EOF';

interface Token {
  type: TokenType;
  value: string | number;
}

type ExprValue = number | string | boolean | unknown[] | Record<string, unknown> | undefined;
type Variables = Record<string, ExprValue>;
type ExprFn = (...args: ExprValue[]) => ExprValue;

// ── Tokenizer ────────────────────────────────────────────────────────

function tokenize(input: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;

  while (i < input.length) {
    const ch = input[i];

    // Whitespace
    if (/\s/.test(ch)) {
      i++;
      continue;
    }

    // Numbers (integers and decimals)
    if (/[0-9]/.test(ch) || (ch === '.' && i + 1 < input.length && /[0-9]/.test(input[i + 1]))) {
      let num = '';
      while (i < input.length && /[0-9.]/.test(input[i])) {
        num += input[i++];
      }
      tokens.push({ type: 'number', value: parseFloat(num) });
      continue;
    }

    // Strings (single or double quoted)
    if (ch === '"' || ch === "'") {
      const quote = ch;
      i++;
      let str = '';
      while (i < input.length && input[i] !== quote) {
        if (input[i] === '\\' && i + 1 < input.length) {
          i++;
          str += input[i];
        } else {
          str += input[i];
        }
        i++;
      }
      i++; // closing quote
      tokens.push({ type: 'string', value: str });
      continue;
    }

    // Identifiers
    if (/[a-zA-Z_]/.test(ch)) {
      let ident = '';
      while (i < input.length && /[a-zA-Z0-9_]/.test(input[i])) {
        ident += input[i++];
      }
      tokens.push({ type: 'ident', value: ident });
      continue;
    }

    // Two-character operators
    if (i + 1 < input.length) {
      const two = ch + input[i + 1];
      if (two === '**' || two === '<=' || two === '>=' || two === '==' || two === '!=' || two === '&&' || two === '||') {
        tokens.push({ type: two as TokenType, value: two });
        i += 2;
        continue;
      }
    }

    // Single-character operators
    if ('+-*/%()<>,?:!'.includes(ch)) {
      tokens.push({ type: ch as TokenType, value: ch });
      i++;
      continue;
    }

    throw new Error(`Unexpected character: ${ch}`);
  }

  tokens.push({ type: 'EOF', value: '' });
  return tokens;
}

// ── Recursive Descent Parser / Evaluator ─────────────────────────────
//
// Grammar (precedence low to high):
//   ternary     -> logical_or ('?' ternary ':' ternary)?
//   logical_or  -> logical_and ('||' logical_and)*
//   logical_and -> equality ('&&' equality)*
//   equality    -> comparison (('==' | '!=') comparison)*
//   comparison  -> addition (('<' | '>' | '<=' | '>=') addition)*
//   addition    -> multiply (('+' | '-') multiply)*
//   multiply    -> power (('*' | '/' | '%') power)*
//   power       -> unary ('**' unary)*
//   unary       -> ('-' | '!') unary | call
//   call        -> primary ('(' args ')')?
//   primary     -> NUMBER | STRING | IDENT | '(' ternary ')'

class ExpressionEvaluator {
  private tokens: Token[];
  private pos = 0;
  private vars: Variables;
  private funcs: Record<string, ExprFn>;

  constructor(tokens: Token[], vars: Variables, funcs: Record<string, ExprFn>) {
    this.tokens = tokens;
    this.vars = vars;
    this.funcs = funcs;
  }

  private peek(): Token {
    return this.tokens[this.pos];
  }

  private advance(): Token {
    const t = this.tokens[this.pos];
    this.pos++;
    return t;
  }

  private expect(type: TokenType): Token {
    const t = this.peek();
    if (t.type !== type) {
      throw new Error(`Expected ${type}, got ${t.type}`);
    }
    return this.advance();
  }

  run(): ExprValue {
    const result = this.ternary();
    if (this.peek().type !== 'EOF') {
      throw new Error(`Unexpected token: ${this.peek().type}`);
    }
    return result;
  }

  private ternary(): ExprValue {
    const cond = this.logicalOr();
    if (this.peek().type === '?') {
      this.advance();
      const consequent = this.ternary();
      this.expect(':');
      const alternate = this.ternary();
      return toBool(cond) ? consequent : alternate;
    }
    return cond;
  }

  private logicalOr(): ExprValue {
    let left = this.logicalAnd();
    while (this.peek().type === '||') {
      this.advance();
      const right = this.logicalAnd();
      left = toBool(left) || toBool(right);
    }
    return left;
  }

  private logicalAnd(): ExprValue {
    let left = this.equality();
    while (this.peek().type === '&&') {
      this.advance();
      const right = this.equality();
      left = toBool(left) && toBool(right);
    }
    return left;
  }

  private equality(): ExprValue {
    let left = this.comparison();
    while (this.peek().type === '==' || this.peek().type === '!=') {
      const op = this.advance().type;
      const right = this.comparison();
      if (op === '==') left = left === right;
      else left = left !== right;
    }
    return left;
  }

  private comparison(): ExprValue {
    let left = this.addition();
    while (
      this.peek().type === '<' ||
      this.peek().type === '>' ||
      this.peek().type === '<=' ||
      this.peek().type === '>='
    ) {
      const op = this.advance().type;
      const right = this.addition();
      const l = toNum(left);
      const r = toNum(right);
      if (op === '<') left = l < r;
      else if (op === '>') left = l > r;
      else if (op === '<=') left = l <= r;
      else left = l >= r;
    }
    return left;
  }

  private addition(): ExprValue {
    let left = this.multiply();
    while (this.peek().type === '+' || this.peek().type === '-') {
      const op = this.advance().type;
      const right = this.multiply();
      if (op === '+') left = toNum(left) + toNum(right);
      else left = toNum(left) - toNum(right);
    }
    return left;
  }

  private multiply(): ExprValue {
    let left = this.power();
    while (this.peek().type === '*' || this.peek().type === '/' || this.peek().type === '%') {
      const op = this.advance().type;
      const right = this.power();
      if (op === '*') left = toNum(left) * toNum(right);
      else if (op === '/') {
        const d = toNum(right);
        left = d === 0 ? 0 : toNum(left) / d;
      } else left = toNum(left) % toNum(right);
    }
    return left;
  }

  private power(): ExprValue {
    const base = this.unary();
    if (this.peek().type === '**') {
      this.advance();
      const exp = this.unary();
      return Math.pow(toNum(base), toNum(exp));
    }
    return base;
  }

  private unary(): ExprValue {
    if (this.peek().type === '-') {
      this.advance();
      return -toNum(this.unary());
    }
    if (this.peek().type === '!') {
      this.advance();
      return !toBool(this.unary());
    }
    return this.call();
  }

  private call(): ExprValue {
    const token = this.peek();

    // Function call: ident(args...)
    if (token.type === 'ident' && this.pos + 1 < this.tokens.length && this.tokens[this.pos + 1].type === '(') {
      const name = String(token.value);
      this.advance(); // ident
      this.advance(); // (
      const args: ExprValue[] = [];
      if (this.peek().type !== ')') {
        args.push(this.ternary());
        while (this.peek().type === ',') {
          this.advance();
          args.push(this.ternary());
        }
      }
      this.expect(')');

      const fn = this.funcs[name];
      if (!fn) throw new Error(`Unknown function: ${name}`);
      return fn(...args);
    }

    return this.primary();
  }

  private primary(): ExprValue {
    const token = this.peek();

    if (token.type === 'number') {
      this.advance();
      return token.value as number;
    }

    if (token.type === 'string') {
      this.advance();
      return token.value as string;
    }

    if (token.type === 'ident') {
      this.advance();
      const name = String(token.value);
      // Boolean literals
      if (name === 'true') return true;
      if (name === 'false') return false;
      // Variable lookup
      if (name in this.vars) return this.vars[name];
      // Also check functions (may be passed as variable)
      if (name in this.funcs) return undefined;
      throw new Error(`Unknown variable: ${name}`);
    }

    if (token.type === '(') {
      this.advance();
      const val = this.ternary();
      this.expect(')');
      return val;
    }

    throw new Error(`Unexpected token: ${token.type}`);
  }
}

// ── Helpers ──────────────────────────────────────────────────────────

function toNum(v: ExprValue): number {
  if (typeof v === 'number') return v;
  if (typeof v === 'boolean') return v ? 1 : 0;
  const n = Number(v);
  return isNaN(n) ? 0 : n;
}

function toBool(v: ExprValue): boolean {
  if (typeof v === 'boolean') return v;
  if (typeof v === 'number') return v !== 0;
  if (typeof v === 'string') return v.length > 0;
  if (v === undefined || v === null) return false;
  return true;
}

function evaluate(expression: string, vars: Variables, funcs: Record<string, ExprFn>): ExprValue {
  const tokens = tokenize(expression);
  const evaluator = new ExpressionEvaluator(tokens, vars, funcs);
  return evaluator.run();
}

// ── Aggregate functions ──────────────────────────────────────────────
function sumFn(arr: any, field: any): number {
  if (!Array.isArray(arr)) return 0;
  return arr.reduce((acc: number, item: any) => {
    const val = Number(item?.[String(field)]);
    return acc + (isNaN(val) ? 0 : val);
  }, 0);
}

function countFn(arr: any, field?: any, matchValue?: any): number {
  if (!Array.isArray(arr)) return 0;
  if (field === undefined) return arr.length;
  return arr.filter((item: any) => item?.[String(field)] === matchValue).length;
}

function avgFn(arr: any, field: any): number {
  if (!Array.isArray(arr) || arr.length === 0) return 0;
  return sumFn(arr, field) / arr.length;
}

function minFn(arr: any, field: any): number {
  if (!Array.isArray(arr) || arr.length === 0) return 0;
  const values = arr.flatMap((item: any) => {
    const value = Number(item?.[String(field)]);
    return isNaN(value) ? [] : [value];
  });
  return values.length > 0 ? Math.min(...values) : 0;
}

function maxFn(arr: any, field: any): number {
  if (!Array.isArray(arr) || arr.length === 0) return 0;
  const values = arr.flatMap((item: any) => {
    const value = Number(item?.[String(field)]);
    return isNaN(value) ? [] : [value];
  });
  return values.length > 0 ? Math.max(...values) : 0;
}

function percentFn(part: any, total: any): number {
  const p = Number(part);
  const t = Number(total);
  if (t === 0) return 0;
  return (p / t) * 100;
}

const builtinFunctions: Record<string, ExprFn> = {
  sum: sumFn as ExprFn,
  count: countFn as ExprFn,
  avg: avgFn as ExprFn,
  min: minFn as ExprFn,
  max: maxFn as ExprFn,
  percent: percentFn as ExprFn,
};

// ── Public API ───────────────────────────────────────────────────────

/**
 * Evaluate a stat expression against data items.
 *
 * Supported functions: sum, count, avg, min, max, percent
 * Supported operators: +, -, *, /, <, >, <=, >=, ==, !=, ?:
 *
 * @returns Computed numeric value, or 0 on error
 */
function computeStatValue(
  expression: string,
  items: Record<string, unknown>[],
): number {
  try {
    const result = evaluate(
      expression,
      { items },
      builtinFunctions,
    );
    return typeof result === 'number' && isFinite(result) ? result : 0;
  } catch (err) {
    console.warn(`computeStatValue failed for "${expression}":`, err);
    return 0;
  }
}

/**
 * Evaluate a color rule expression.
 *
 * The expression should be a ternary that returns a color name string.
 * Variables: `value` (the stat value), `percent` (optional percentage).
 *
 * Example: "value < 0 ? 'rose' : 'emerald'"
 *
 * @returns Color name string, or '' on error
 */
export function evaluateColorRule(
  rule: string,
  value: number,
  percent?: number,
): string {
  try {
    const result = evaluate(
      rule,
      { value, percent: percent ?? 0 },
      builtinFunctions,
    );
    return typeof result === 'string' ? result : '';
  } catch (err) {
    console.warn(`evaluateColorRule failed for "${rule}":`, err);
    return '';
  }
}

/**
 * Format a numeric stat value for display.
 */
export function formatStatValue(
  value: number,
  format?: 'currency' | 'percentage' | 'number',
): string {
  switch (format) {
    case 'currency':
      return (
        '$' +
        value.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      );
    case 'percentage':
      return value.toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%';
    case 'number':
    default:
      return value.toLocaleString();
  }
}
