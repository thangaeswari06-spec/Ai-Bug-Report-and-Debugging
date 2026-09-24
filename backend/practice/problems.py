"""
problems.py
-----------
Practice problems + per-language starter templates.

Every problem reads from stdin and prints to stdout, so the SAME test cases
work for all 10 languages. Two input kinds keep the starter templates small:

  ints    one line of space-separated integers  -> `nums`
  string  one line of text                      -> `s`

All numbers stay below 2**53 so JavaScript is exact too.
"""

PROBLEMS = [
    {
        "id": "sum-two", "title": "Sum of Two Numbers", "difficulty": "Easy", "kind": "ints", "topic": "Basics",
        "statement": "Read two integers `a` and `b` and print their sum.",
        "tests": [("3 4", "7"), ("-5 2", "-3"), ("0 0", "0"), ("1000000 2500000", "3500000"), ("-10 -20", "-30")],
    },
    {
        "id": "even-odd", "title": "Even or Odd", "difficulty": "Easy", "kind": "ints", "topic": "Conditions",
        "statement": "Read one integer `n`. Print `Even` if it is even, otherwise print `Odd`.",
        "tests": [("4", "Even"), ("7", "Odd"), ("0", "Even"), ("-3", "Odd"), ("100001", "Odd")],
    },
    {
        "id": "max-list", "title": "Largest Number", "difficulty": "Easy", "kind": "ints", "topic": "Arrays",
        "statement": "Read a list of integers on one line and print the largest one.",
        "tests": [("3 9 2", "9"), ("-4 -1 -8", "-1"), ("5", "5"), ("10 10 10", "10"), ("1 2 3 4 5 6 7 8 9 100 3", "100")],
    },
    {
        "id": "factorial", "title": "Factorial", "difficulty": "Easy", "kind": "ints", "topic": "Loops",
        "statement": "Read `n` (0 ≤ n ≤ 15) and print n! (n factorial). Note: 0! = 1.",
        "tests": [("5", "120"), ("0", "1"), ("1", "1"), ("10", "3628800"), ("15", "1307674368000")],
    },
    {
        "id": "fizzbuzz", "title": "FizzBuzz", "difficulty": "Easy", "kind": "ints", "topic": "Loops",
        "statement": "Read `n`. For every i from 1 to n print one line: `FizzBuzz` if i is divisible by 3 and 5, `Fizz` if divisible by 3, `Buzz` if divisible by 5, otherwise the number i.",
        "tests": [("5", "1\n2\nFizz\n4\nBuzz"), ("1", "1"),
                  ("15", "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz"),
                  ("3", "1\n2\nFizz")],
    },
    {
        "id": "reverse-string", "title": "Reverse a String", "difficulty": "Easy", "kind": "string", "topic": "Strings",
        "statement": "Read one line of text and print it reversed.",
        "tests": [("hello", "olleh"), ("a", "a"), ("racecar", "racecar"), ("Bug Fixer", "rexiF guB"), ("12345", "54321")],
    },
    {
        "id": "count-vowels", "title": "Count the Vowels", "difficulty": "Easy", "kind": "string", "topic": "Strings",
        "statement": "Read one line of text and print how many vowels (a, e, i, o, u — upper or lower case) it contains.",
        "tests": [("hello", "2"), ("rhythm", "0"), ("AEIOU", "5"), ("Programming Language", "7"), ("bcd", "0")],
    },
    {
        "id": "palindrome", "title": "Palindrome Check", "difficulty": "Medium", "kind": "string", "topic": "Strings",
        "statement": "Read one word. Print `Yes` if it reads the same forwards and backwards (ignore upper/lower case), otherwise `No`.",
        "tests": [("madam", "Yes"), ("Level", "Yes"), ("hello", "No"), ("a", "Yes"), ("Abba", "Yes"), ("abca", "No")],
    },
    {
        "id": "fibonacci", "title": "Nth Fibonacci", "difficulty": "Medium", "kind": "ints", "topic": "Loops",
        "statement": "Read `n` (0 ≤ n ≤ 40) and print the nth Fibonacci number, where F(0)=0 and F(1)=1.",
        "tests": [("0", "0"), ("1", "1"), ("10", "55"), ("20", "6765"), ("40", "102334155")],
    },
    {
        "id": "prime-check", "title": "Prime or Not", "difficulty": "Medium", "kind": "ints", "topic": "Math",
        "statement": "Read `n` (1 ≤ n ≤ 1,000,000). Print `Prime` if n is a prime number, otherwise `Not Prime`. Remember: 1 is not prime.",
        "tests": [("7", "Prime"), ("1", "Not Prime"), ("2", "Prime"), ("15", "Not Prime"), ("999983", "Prime"), ("1000000", "Not Prime")],
    },
]

VISIBLE_TESTS = 2  # first N tests are shown to the user; the rest are hidden until submit


# ---------------------------------------------------------------- starters
_T = {}

_T["python"] = {
    "ints": "nums = list(map(int, input().split()))\n\n# TODO: solve the problem using `nums` and print the answer\n",
    "string": "s = input()\n\n# TODO: solve the problem using `s` and print the answer\n",
}
_JS_HEAD = 'const lines = require("fs").readFileSync(0, "utf8").split("\\n");\n'
_T["javascript"] = {
    "ints": _JS_HEAD + 'const nums = lines[0].trim().split(/\\s+/).map(Number);\n\n// TODO: solve the problem using `nums` and console.log the answer\n',
    "string": _JS_HEAD + 'const s = lines[0].replace(/\\r$/, "");\n\n// TODO: solve the problem using `s` and console.log the answer\n',
}
_T["typescript"] = {
    "ints": _JS_HEAD.replace("const lines", "const lines: string[]") + 'const nums: number[] = lines[0].trim().split(/\\s+/).map(Number);\n\n// TODO: solve the problem using `nums` and console.log the answer\n',
    "string": _JS_HEAD.replace("const lines", "const lines: string[]") + 'const s: string = lines[0].replace(/\\r$/, "");\n\n// TODO: solve the problem using `s` and console.log the answer\n',
}
_T["java"] = {
    "ints": 'import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        long[] nums = Arrays.stream(sc.nextLine().trim().split("\\\\s+")).mapToLong(Long::parseLong).toArray();\n\n        // TODO: solve the problem using nums and System.out.println the answer\n    }\n}\n',
    "string": 'import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        String s = sc.hasNextLine() ? sc.nextLine() : "";\n\n        // TODO: solve the problem using s and System.out.println the answer\n    }\n}\n',
}
_T["c"] = {
    "ints": '#include <stdio.h>\n\nint main(void) {\n    long long nums[1000];\n    int count = 0;\n    while (count < 1000 && scanf("%lld", &nums[count]) == 1) count++;\n\n    /* TODO: solve the problem using nums[0..count-1] and printf the answer */\n    return 0;\n}\n',
    "string": '#include <stdio.h>\n#include <string.h>\n\nint main(void) {\n    char s[1001];\n    if (!fgets(s, sizeof s, stdin)) s[0] = \'\\0\';\n    s[strcspn(s, "\\r\\n")] = \'\\0\';\n\n    /* TODO: solve the problem using s and printf the answer */\n    return 0;\n}\n',
}
_T["cpp"] = {
    "ints": '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    vector<long long> nums;\n    long long x;\n    while (cin >> x) nums.push_back(x);\n\n    // TODO: solve the problem using nums and cout the answer\n    return 0;\n}\n',
    "string": '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    string s;\n    getline(cin, s);\n    if (!s.empty() && s.back() == \'\\r\') s.pop_back();\n\n    // TODO: solve the problem using s and cout the answer\n    return 0;\n}\n',
}
_T["csharp"] = {
    "ints": 'using System;\nusing System.Linq;\n\nclass Program\n{\n    static void Main()\n    {\n        long[] nums = Console.ReadLine().Trim().Split(\' \', StringSplitOptions.RemoveEmptyEntries).Select(long.Parse).ToArray();\n\n        // TODO: solve the problem using nums and Console.WriteLine the answer\n    }\n}\n',
    "string": 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        string s = Console.ReadLine() ?? "";\n\n        // TODO: solve the problem using s and Console.WriteLine the answer\n    }\n}\n',
}
_T["go"] = {
    "ints": 'package main\n\nimport (\n\t"bufio"\n\t"fmt"\n\t"os"\n\t"strconv"\n\t"strings"\n)\n\nfunc main() {\n\treader := bufio.NewReader(os.Stdin)\n\tline, _ := reader.ReadString(\'\\n\')\n\tvar nums []int64\n\tfor _, f := range strings.Fields(line) {\n\t\tv, _ := strconv.ParseInt(f, 10, 64)\n\t\tnums = append(nums, v)\n\t}\n\n\t// TODO: solve the problem using nums and fmt.Println the answer\n\t_ = nums\n\t_ = fmt.Sprint\n}\n',
    "string": 'package main\n\nimport (\n\t"bufio"\n\t"fmt"\n\t"os"\n\t"strings"\n)\n\nfunc main() {\n\treader := bufio.NewReader(os.Stdin)\n\ts, _ := reader.ReadString(\'\\n\')\n\ts = strings.TrimRight(s, "\\r\\n")\n\n\t// TODO: solve the problem using s and fmt.Println the answer\n\t_ = s\n\t_ = fmt.Sprint\n}\n',
}
_T["rust"] = {
    "ints": 'use std::io::{self, Read};\n\nfn main() {\n    let mut input = String::new();\n    io::stdin().read_to_string(&mut input).unwrap();\n    let nums: Vec<i64> = input.split_whitespace().map(|x| x.parse().unwrap()).collect();\n\n    // TODO: solve the problem using nums and println! the answer\n    let _ = &nums;\n}\n',
    "string": 'use std::io;\n\nfn main() {\n    let mut s = String::new();\n    io::stdin().read_line(&mut s).unwrap();\n    let s = s.trim_end_matches(&[\'\\r\', \'\\n\'][..]);\n\n    // TODO: solve the problem using s and println! the answer\n    let _ = s;\n}\n',
}
_T["php"] = {
    "ints": '<?php\n$nums = array_map(\'intval\', preg_split(\'/\\s+/\', trim(fgets(STDIN))));\n\n// TODO: solve the problem using $nums and echo the answer\n',
    "string": '<?php\n$s = rtrim(fgets(STDIN), "\\r\\n");\n\n// TODO: solve the problem using $s and echo the answer\n',
}

STARTERS = _T


def get_problem(problem_id: str):
    return next((p for p in PROBLEMS if p["id"] == problem_id), None)


def starter_for(problem: dict, language: str) -> str:
    return STARTERS[language][problem["kind"]]


def public_problem(p: dict, include_starter_for: str | None = None) -> dict:
    out = {
        "id": p["id"], "title": p["title"], "difficulty": p["difficulty"], "topic": p["topic"],
        "statement": p["statement"], "kind": p["kind"],
        "examples": [{"input": i, "output": o} for i, o in p["tests"][:VISIBLE_TESTS]],
        "total_tests": len(p["tests"]),
    }
    if include_starter_for:
        out["starter"] = starter_for(p, include_starter_for)
    return out
