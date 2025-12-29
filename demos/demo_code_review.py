"""
Code Review Demo: Agent reviews code files, committing findings per file.

This demo simulates a code review scenario where:
1. Agent receives multiple code files to review
2. Reviews each file, committing findings before moving to next
3. Uses branches to separate concerns (security, performance, style)
4. Tags final review summary

Shows how commits preserve review context while keeping working memory lean.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctx_cli import CTX_CLI_TOOL, execute_command
from ctx_store import ContextStore, Message

SYSTEM_PROMPT = """You are a senior code reviewer performing a thorough code review.

You have ctx_cli for context management. Use it strategically:

## Review Strategy:
1. Create a branch for the review (e.g., review-auth-module)
2. Review each file, then COMMIT your findings before moving to next file
3. Your commit messages should capture:
   - Issues found (bugs, security, performance)
   - Suggestions for improvement
   - Good patterns observed

## Commands you'll use:
- checkout -b review-xyz -m "Starting review of XYZ" - Start review branch
- commit -m "file.py: [issues and findings]" - Save review of one file
- tag review-complete -m "Summary" - Mark review as complete

## Review Checklist per file:
- Security vulnerabilities
- Performance issues
- Code style/readability
- Error handling
- Edge cases

Be thorough but concise in commits. Each commit = one file's review."""

# Simulated code files for review
CODE_FILES = {
    "auth.py": '''
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    user = db.execute(query).fetchone()
    if user:
        session['user_id'] = user['id']
        return True
    return False

def reset_password(email):
    token = str(random.randint(1000, 9999))
    db.execute(f"UPDATE users SET reset_token='{token}' WHERE email='{email}'")
    send_email(email, f"Your reset code is {token}")
''',
    "api.py": '''
@app.route('/api/users/<id>')
def get_user(id):
    user = db.execute(f"SELECT * FROM users WHERE id={id}").fetchone()
    return jsonify(dict(user))

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    db.execute(f"INSERT INTO users (name, email) VALUES ('{data['name']}', '{data['email']}')")
    return jsonify({"status": "created"})

@app.route('/api/admin/delete_all', methods=['POST'])
def delete_all_users():
    db.execute("DELETE FROM users")
    return jsonify({"status": "deleted"})
''',
    "utils.py": '''
def process_file(filename):
    with open(filename) as f:
        content = f.read()
    result = eval(content)
    return result

def run_command(cmd):
    import os
    return os.system(cmd)

def log_error(error):
    print(f"Error: {error}")
''',
    "cache.py": '''
cache = {}

def get_cached(key):
    return cache.get(key)

def set_cached(key, value, ttl=3600):
    cache[key] = value
    # TODO: implement TTL

def clear_cache():
    global cache
    cache = {}

def get_or_compute(key, compute_fn):
    if key not in cache:
        cache[key] = compute_fn()
    return cache[key]
'''
}


def run_code_review():
    """Run code review demo."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY")
        return

    client = OpenAI(api_key=api_key)
    store = ContextStore()
    tools = [CTX_CLI_TOOL]

    def chat(user_message: str, label: str = "") -> str:
        if label:
            print(f"\n{'━' * 60}")
            print(f"  {label}")
            print(f"{'━' * 60}")

        store.add_message(Message(role="user", content=user_message))

        for _ in range(10):
            context = store.get_context(SYSTEM_PROMPT)

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=context,
                tools=tools,
            )

            message = response.choices[0].message

            if message.tool_calls:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                    tool_calls=[tc.model_dump() for tc in message.tool_calls]
                ))

                tool_results = []
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "ctx_cli":
                        args = json.loads(tool_call.function.arguments)
                        result, _ = execute_command(store, args["command"])
                        cmd = args["command"]
                        if "commit" in cmd:
                            print(f"  💾 COMMIT: {cmd[11:70]}...")
                        elif "tag" in cmd:
                            print(f"  🏷️  TAG: {cmd}")
                        else:
                            print(f"  [ctx] {cmd[:60]}")
                        tool_results.append((tool_call.id, result))

                for tool_id, result in tool_results:
                    store.add_message(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tool_id,
                    ))
            else:
                store.add_message(Message(
                    role="assistant",
                    content=message.content or "",
                ))
                response_short = (message.content or "")[:300]
                if len(message.content or "") > 300:
                    response_short += "..."
                print(f"\n  {response_short}")
                return message.content or ""

        return "[Max rounds]"

    print("=" * 70)
    print("CODE REVIEW DEMO: Reviewing Multiple Files with Context Management")
    print("=" * 70)
    print("\nSimulating review of a Python web application with security issues...")

    # Start the review
    chat("""
    I need you to perform a security-focused code review of a Python web application.

    Start by creating a review branch, then I'll give you the files one by one.
    """, label="SETUP: Initialize Review")

    # Review each file
    for filename, code in CODE_FILES.items():
        chat(f"""
    Review this file: {filename}

    ```python
{code}
    ```

    After reviewing, commit your findings for this file before I give you the next one.
    Focus on: security vulnerabilities, bugs, and critical issues.
    """, label=f"REVIEW: {filename}")

    # Final summary
    chat("""
    You've reviewed all files. Now:
    1. Create a summary of the most critical issues found
    2. Tag this review as complete with a severity assessment
    3. Show me the final status
    """, label="SUMMARY: Final Assessment")

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("CODE REVIEW RESULTS")
    print("=" * 70)

    print("\n📋 Review Commits:")
    result, _ = store.log(limit=10)
    for line in result.split("\n"):
        if line.strip():
            print(f"  {line}")

    print("\n🏷️  Tags:")
    if store.tags:
        for name, tag in store.tags.items():
            print(f"  {name}: {tag.description[:60]}...")
    else:
        print("  (no tags)")

    print("\n📊 Statistics:")
    print(f"  Files reviewed: {len(CODE_FILES)}")
    print(f"  Commits made: {sum(len(b.commits) for b in store.branches.values())}")
    print(f"  Context operations: {len(store.events)}")

    # Count security issues mentioned
    security_keywords = ["SQL injection", "injection", "eval", "os.system", "security", "vulnerable"]
    issues_found = 0
    for branch in store.branches.values():
        for commit in branch.commits:
            for keyword in security_keywords:
                if keyword.lower() in commit.message.lower():
                    issues_found += 1
                    break
    print(f"  Security-related commits: {issues_found}")


if __name__ == "__main__":
    run_code_review()
