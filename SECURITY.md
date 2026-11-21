# Security & deployment notes

Kayock Voice is designed for **trusted, local deployments**. The example deployment does not implement API-key authentication and the core server accepts permissive CORS requests. **Do not expose ports 8766 or 8768 directly to the public internet.** Restrict access with your firewall, trusted-network binding, or a properly configured reverse proxy with authentication.

Generate unique TLS certificates and private keys on each machine. Never commit keys, tokens, private recordings, or custom voice-model weights. RVC/Piper voice models may have independent usage and redistribution restrictions.

If you discover a security concern, contact the repository maintainer privately rather than publishing credentials or a working exploit in an issue.
