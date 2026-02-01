# IAP_A1
<pre>
Project Structure:
A1/
├── src/
│   ├── server/
│   │   ├── server.py       # Main thread-based logic
│   │   └── utils.py        # Auth & hashing (bcrypt)
│   └── client/
│       └── client.py       # Threaded client with TLS support
├── docker/
│   ├── Dockerfile          # Server image configuration
│   └── docker-compose.yml  # Orchestrates Servers + Redis
├── docs/
│   └── report.pdf          # Your 2-4 page design report
├── requirements.txt        # bcrypt, redis, etc.
└── README.md               # Setup and testing instructions
</pre>
