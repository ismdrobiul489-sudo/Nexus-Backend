import socket
import json

def get_ips(domain):
    try:
        # Get all address info for the domain
        info = socket.getaddrinfo(domain, None)
        ips = list(set([item[4][0] for item in info]))
        return ips
    except Exception as e:
        return [f"Error: {str(e)}"]

domains = [
    "graph.facebook.com",
    "graph-video.facebook.com",
    "rupload.facebook.com",
    "www.facebook.com",
    "www.googleapis.com",
    "accounts.google.com",
    "oauth2.googleapis.com",
    "generativelanguage.googleapis.com",
    "suggestqueries.google.com",
    "upload.youtube.com",
    "a.rtmp.youtube.com",
    "b.rtmp.youtube.com",
    "huggingface.co",
    "api-inference.huggingface.co",
    "sora.com",
    "sora.chatgpt.com",
    "openrouter.ai",
    "api.groq.com",
    "cloud.leonardo.ai",
    "ai.api.nvidia.com",
    "newsdata.io",
    "gnews.io",
    "api.dailymotion.com",
    "api.open-meteo.com",
    "ui-avatars.com"
]

def main():
    print("--- DNS Lookup Tool for Domain Bypass ---\n")
    results = {}
    for domain in domains:
        print(f"Checking: {domain}...")
        ips = get_ips(domain)
        results[domain] = ips
        for ip in ips:
            print(f"  -> {ip}")
    
    # Save to a separate JSON for easy reference
    with open("domain_ips.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\n[Done] Results saved to 'domain_ips.json'. This file is separate from your main project logic.")

if __name__ == "__main__":
    main()
