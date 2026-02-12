#!/usr/bin/env python3
"""
Performance Benchmark for reCAPTCHAv2 Solver
Analyzes session logs and measures model inference times
"""

import os
import csv
import time
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
from collections import defaultdict

# Model imports
try:
    from models.YOLO_Classification import predict as predict_classification
    from models.YOLO_Segment import predict as predict_segment
except ImportError as e:
    print(f"Warning: Could not import models: {e}")
    predict_classification = None
    predict_segment = None

class BenchmarkAnalyzer:
    def __init__(self):
        self.sessions_path = Path("/workspaces/reCAPTCHAv2-solver/Sessions")
        self.results = {
            "session_analysis": {},
            "model_inference_times": {},
            "aggregate_metrics": {}
        }
    
    def analyze_session_logs(self):
        """Analyze all session logs for success rates and performance metrics"""
        print("\n" + "="*80)
        print("SESSION LOG ANALYSIS")
        print("="*80)
        
        session_stats = defaultdict(lambda: {
            "total": 0,
            "solved": 0,
            "failed": 0,
            "times": [],
            "errors": []
        })
        
        # Iterate through all session directories
        for session_dir in sorted(self.sessions_path.glob("**/")):
            if session_dir.is_dir() and any(session_dir.glob("*.csv")):
                session_name = session_dir.relative_to(self.sessions_path)
                
                # Process all CSV files in the session
                csv_files = list(session_dir.glob("*.csv"))
                for csv_file in sorted(csv_files):
                    self._process_log_file(str(csv_file), session_name, session_stats)
        
        # Print summary statistics
        self._print_session_summary(session_stats)
        self.results["session_analysis"] = {str(k): v for k, v in session_stats.items()}
        
        return session_stats
    
    def _process_log_file(self, log_path, session_name, session_stats):
        """Process individual log file"""
        try:
            df = pd.read_csv(log_path, header=None)
            
            # Each row represents a solved CAPTCHA attempt
            for _, row in df.iterrows():
                session_stats[session_name]["total"] += 1
                session_stats[session_name]["solved"] += 1
                
                # Log format: timestamp, type, category
                # If all rows are successful attempts, mark them as solved
        
        except Exception as e:
            session_stats[session_name]["errors"].append(str(e))
    
    def _print_session_summary(self, session_stats):
        """Print formatted summary of session statistics"""
        print("\nSession Statistics:")
        print("-" * 80)
        print(f"{'Session':<30} {'Total':<8} {'Solved':<8} {'Failed':<8} {'Success %':<12}")
        print("-" * 80)
        
        total_solved = 0
        total_attempts = 0
        all_times = []
        
        for session_name in sorted(session_stats.keys()):
            stats = session_stats[session_name]
            solved = stats["solved"]
            total = stats["total"]
            success_rate = (solved / total * 100) if total > 0 else 0
            
            print(f"{str(session_name):<30} {total:<8} {solved:<8} {stats['failed']:<8} {success_rate:<11.2f}%")
            
            total_solved += solved
            total_attempts += total
            all_times.extend(stats["times"])
        
        print("-" * 80)
        overall_rate = (total_solved / total_attempts * 100) if total_attempts > 0 else 0
        print(f"{'OVERALL':<30} {total_attempts:<8} {total_solved:<8} {total_attempts - total_solved:<8} {overall_rate:<11.2f}%")
        
        if all_times:
            print(f"\nTiming Statistics (from logs):")
            print(f"  Mean time: {np.mean(all_times):.3f}s")
            print(f"  Median time: {np.median(all_times):.3f}s")
            print(f"  Min time: {np.min(all_times):.3f}s")
            print(f"  Max time: {np.max(all_times):.3f}s")
            print(f"  Std dev: {np.std(all_times):.3f}s")
    
    def benchmark_model_inference(self):
        """Benchmark model inference times"""
        if predict_classification is None or predict_segment is None:
            print("\n" + "="*80)
            print("MODEL INFERENCE BENCHMARKING")
            print("="*80)
            print("Warning: Models not available for benchmarking")
            return
        
        print("\n" + "="*80)
        print("MODEL INFERENCE BENCHMARKING")
        print("="*80)
        
        # Create a dummy image for testing
        try:
            from PIL import Image
            import numpy as np
            
            # Create test image
            test_image = Image.new('RGB', (416, 416), color='red')
            
            # Benchmark Classification Model
            print("\nYOLO Classification Model Inference:")
            print("-" * 40)
            inference_times = []
            
            for i in range(5):
                start = time.time()
                try:
                    result = predict_classification(test_image)
                    inference_times.append(time.time() - start)
                except Exception as e:
                    print(f"  Inference {i+1}: Error - {e}")
            
            if inference_times:
                self.results["model_inference_times"]["classification"] = {
                    "mean": np.mean(inference_times),
                    "median": np.median(inference_times),
                    "min": np.min(inference_times),
                    "max": np.max(inference_times),
                    "std": np.std(inference_times),
                    "samples": len(inference_times)
                }
                print(f"  Mean inference time: {np.mean(inference_times)*1000:.2f}ms")
                print(f"  Median: {np.median(inference_times)*1000:.2f}ms")
                print(f"  Range: {np.min(inference_times)*1000:.2f}ms - {np.max(inference_times)*1000:.2f}ms")
            
            # Benchmark Segmentation Model
            print("\nYOLO Segmentation Model Inference:")
            print("-" * 40)
            inference_times = []
            
            for i in range(5):
                start = time.time()
                try:
                    result = predict_segment(test_image)
                    inference_times.append(time.time() - start)
                except Exception as e:
                    print(f"  Inference {i+1}: Error - {e}")
            
            if inference_times:
                self.results["model_inference_times"]["segmentation"] = {
                    "mean": np.mean(inference_times),
                    "median": np.median(inference_times),
                    "min": np.min(inference_times),
                    "max": np.max(inference_times),
                    "std": np.std(inference_times),
                    "samples": len(inference_times)
                }
                print(f"  Mean inference time: {np.mean(inference_times)*1000:.2f}ms")
                print(f"  Median: {np.median(inference_times)*1000:.2f}ms")
                print(f"  Range: {np.min(inference_times)*1000:.2f}ms - {np.max(inference_times)*1000:.2f}ms")
        
        except Exception as e:
            print(f"Error benchmarking models: {e}")
    
    def generate_report(self):
        """Generate comprehensive benchmark report"""
        print("\n" + "="*80)
        print("BENCHMARK REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save detailed report
        report_path = Path("/workspaces/reCAPTCHAv2-solver/benchmark_report.json")
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nDetailed report saved to: {report_path}")
        
        return self.results
    
    def run_all_benchmarks(self):
        """Run all benchmark tests"""
        print("\n" + "="*80)
        print("reCAPTCHAv2 SOLVER - PERFORMANCE BENCHMARK")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Analyze existing session logs
        self.analyze_session_logs()
        
        # Benchmark model inference
        self.benchmark_model_inference()
        
        # Generate report
        self.generate_report()
        
        print("\n" + "="*80)
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)


def main():
    analyzer = BenchmarkAnalyzer()
    analyzer.run_all_benchmarks()


if __name__ == "__main__":
    main()
