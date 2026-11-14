"""Minimal MCP client over stdio (JSON-RPC, newline-delimited). Standard library only.

Enough of the protocol for the study: initialize, tools/list, tools/call.
"""
import json, os, subprocess, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
NM = os.path.join(HERE, "node_modules", "@modelcontextprotocol")


class MCPServer:
    def __init__(self, name, argv, env=None, cwd=None):
        self.name, self._id, self._lock = name, 0, threading.Lock()
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1, cwd=cwd, env={**os.environ, **(env or {})})
        self.info = self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                              "clientInfo": {"name": "prism-agent-study", "version": "0.1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.tools = self._rpc("tools/list", {})["tools"]

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n"); self.proc.stdin.flush()

    def _rpc(self, method, params):
        with self._lock:
            self._id += 1
            self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
            while True:
                line = self.proc.stdout.readline()
                if not line: raise RuntimeError(f"MCP server {self.name} closed the connection")
                try: msg = json.loads(line)
                except ValueError: continue
                if msg.get("id") == self._id:
                    if "error" in msg: raise RuntimeError(msg["error"].get("message", "MCP error"))
                    return msg["result"]

    def call(self, tool, args):
        """Returns (text, is_error)."""
        try:
            r = self._rpc("tools/call", {"name": tool, "arguments": args})
        except RuntimeError as e:
            return f"Error: {e}", True
        text = "\n".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        return text, bool(r.get("isError"))

    def close(self):
        try: self.proc.stdin.close(); self.proc.terminate(); self.proc.wait(timeout=5)
        except Exception: self.proc.kill()


def start_servers(db_path, workspace, memory_file):
    """The three no-auth servers of the study: one custom, two reference servers."""
    return [
        MCPServer("shop", [sys.executable, os.path.join(HERE, "shop_mcp.py"), "serve", db_path]),
        MCPServer("filesystem", ["node", os.path.join(NM, "server-filesystem", "dist", "index.js"), workspace], cwd=workspace),
        MCPServer("memory", ["node", os.path.join(NM, "server-memory", "dist", "index.js")],
                  env={"MEMORY_FILE_PATH": memory_file}),
    ]
