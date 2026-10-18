"""
RippleGuard Launcher Script.
Run this script to start the RippleGuard backend and open the dashboard.
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 65)
    print("  🚀 Starting RippleGuard: Multi-Agent Intelligence Layer")
    print("  🔗 FalkorDB Context & Memory Engine")
    print("  🌐 Dashboard: http://127.0.0.1:8000/")
    print("=" * 65)
    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=False)
