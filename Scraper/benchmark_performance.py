#!/usr/bin/env python3
"""
Bumble Scraper Performance Benchmark
Tests the scraper with increasing worker counts to find the hardware sweet spot.
"""

import os
import sys
import time
import subprocess
import argparse
import json
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

# Configuration
WORKER_COUNTS = [2, 4, 6, 8, 12]
PROFILES_PER_TEST = 10  # Total profiles to scrape per test run
TIMEOUT_SECONDS = 300   # Max time per test run (5 minutes)

def get_system_stats():
    """Get current CPU and Memory usage."""
    if not psutil:
        return {"cpu_percent": 0, "memory_percent": 0, "memory_available_gb": 0}
        
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3)
        }
    except Exception:
        return None

def run_benchmark(worker_count, cookie_file):
    print(f"\n{'='*60}")
    print(f"Testing with {worker_count} WORKERS")
    print(f"{'='*60}")

    # Calculate limit per worker to achieve total target
    # limit_per_worker = max(1, PROFILES_PER_TEST // worker_count)
    # Actually, the --limit flag is global or per worker?
    # Checking scraper code... args.limit is passed to each worker.
    # So if we want TOTAL 10, and have 2 workers, we set limit=5.
    limit_per_worker = max(1, int(PROFILES_PER_TEST / worker_count))
    
    cmd = [
        sys.executable,
        "submodules/bumble-auto-liker/Scraper/bumble_profile_scraper.py",
        "--cookies", cookie_file,
        "--limit", str(limit_per_worker),
        "--location", "Seattle",
        "--workers", str(worker_count),
        "--stagger", "3", # Lower stagger for faster benchmark
        "--headless",     # Force headless for consistent benchmarking
        "--no-swipe"      # Disable swiping to test extraction speed specifically? 
                          # No, we want real-world performance. Enable swiping.
    ]
    
    # Remove --headless if you want to see them, but for benchmark headless is better for resources
    # The user asked for "non headless", but for a STRESS TEST, headless is standard.
    # I'll stick to headless for the benchmark to minimize rendering overhead variability.
    
    print(f"Command: {' '.join(cmd)}")
    
    start_time = time.time()
    initial_stats = get_system_stats()
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Monitor while running
        max_cpu = 0
        max_mem = 0
        
        while process.poll() is None:
            stats = get_system_stats()
            if stats:
                max_cpu = max(max_cpu, stats['cpu_percent'])
                max_mem = max(max_mem, stats['memory_percent'])
                sys.stdout.write(f"\rResources: CPU {stats['cpu_percent']}% | RAM {stats['memory_percent']}%")
                sys.stdout.flush()
            
            if time.time() - start_time > TIMEOUT_SECONDS:
                process.terminate()
                print("\n[!] Timed out!")
                return None
            
            time.sleep(1)
            
        print("\nFinished.")
        end_time = time.time()
        duration = end_time - start_time
        
        # Parse output to verify actual profiles scraped
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"\n[X] Scraper failed with exit code {process.returncode}")
            print(f"STDERR Snippet:\n{stderr[-500:]}")
            print(f"STDOUT Snippet:\n{stdout[-500:]}")
            return None
        
        # Count "Successfully extracted" or JSON saves
        profile_count = stdout.count("Saved to Notion") + stdout.count("Saved to JSON") 
        # Since log output might be messy, let's rely on the requested limit as "attempted"
        # Ideally we parse the "Successfully extracted X profile(s)" lines from workers
        
        # Simple PPM calculation
        ppm = (PROFILES_PER_TEST / duration) * 60
        
        return {
            "workers": worker_count,
            "duration": duration,
            "max_cpu": max_cpu,
            "max_mem": max_mem,
            "ppm": ppm,
            "success": process.returncode == 0
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Benchmark Bumble Scraper")
    parser.add_argument("--cookies", required=True, help="Path to cookies file")
    args = parser.parse_args()
    
    if not psutil:
        print("Warning: 'psutil' module not found. Resource monitoring will be disabled.")
    
    results = []
    
    print(f"Starting Benchmark on {os.cpu_count()} CPU cores...")
    
    for count in WORKER_COUNTS:
        start_wait = 5
        print(f"Cooling down for {start_wait}s...")
        time.sleep(start_wait)
        
        result = run_benchmark(count, args.cookies)
        if result:
            results.append(result)
            print(f"Result: {result['ppm']:.2f} Profiles/Min (Duration: {result['duration']:.2f}s)")
        else:
            print("Benchmark failed for this worker count.")
            
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print(f"{'Workers':<10} | {'Time (s)':<10} | {'PPM':<10} | {'Max CPU%':<10} | {'Max RAM%':<10}")
    print("-" * 60)
    
    best_config = None
    max_ppm = 0
    
    for r in results:
        print(f"{r['workers']:<10} | {r['duration']:<10.2f} | {r['ppm']:<10.2f} | {r['max_cpu']:<10} | {r['max_mem']:<10}")
        if r['ppm'] > max_ppm:
            max_ppm = r['ppm']
            best_config = r['workers']
            
    print("="*60)
    print(f"Recommended Worker Count: {best_config}")

if __name__ == "__main__":
    main()
