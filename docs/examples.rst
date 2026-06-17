Examples
========

This page contains practical examples of using ProverCLI.

Example 1: Analyze All Violations
----------------------------------

Group violations by contract and display summary:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()
   violations = api.get_violated_rules("12345678")

   print(f"Total violations: {len(violations)}")

   # Group by contract
   by_contract = {}
   for v in violations:
       contract = v.contract_name or "Unknown"
       if contract not in by_contract:
           by_contract[contract] = []
       by_contract[contract].append(v)

   # Print summary
   for contract, vlist in by_contract.items():
       print(f"\n{contract}: {len(vlist)} violations")
       for v in vlist:
           print(f"  - {v.rule_name}: {v.assert_message}")
           if v.source_location:
               print(f"    Location: {v.source_location}")

Example 2: Monitor Job Progress
--------------------------------

Monitor a running job until completion:

.. code-block:: python

   import time
   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.models import JobStatus

   api = ProverOutputAPI()
   job_id = "12345678"

   print(f"Monitoring job {job_id}...")

   while True:
       status = api.get_job_status(job_id)

       if status == JobStatus.RUNNING:
           print("Job is running...")
           time.sleep(10)
       elif status == JobStatus.SUCCEEDED:
           print("Job completed successfully!")
           violations = api.get_violated_rules(job_id)
           print(f"Found {len(violations)} violations")
           break
       elif status in [JobStatus.FAILED, JobStatus.CANCELED]:
           print(f"Job ended with status: {status}")
           break
       else:
           print(f"Job status: {status}")
           time.sleep(5)

Example 3: Deep Trace Analysis
-------------------------------

Analyze violations with detailed trace information:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()
   violations = api.get_violated_rules("12345678")

   for violation in violations:
       print(f"\n{'='*60}")
       print(f"Analyzing violation: {violation.rule_name}")
       print(f"Method: {violation.method_name}")
       print(f"Message: {violation.assert_message}")

       # Get calltrace
       if violation.has_calltrace:
           trace = api.get_calltrace_for_violation("12345678", violation)
           print(f"\nCalltrace:")
           print(f"  Total frames: {trace.frame_count}")

           # Print first few frames
           for i in range(min(3, trace.frame_count)):
               frame = trace.get_frame(i)
               if frame:
                   print(f"  Frame {i}: {frame.get('name', 'Unknown')}")

       # Get breadcrumbs
       if violation.has_breadcrumbs:
           bc = api.get_breadcrumbs_for_violation("12345678", violation)
           print(f"\nBreadcrumbs:")
           print(f"  Total steps: {bc.total_steps}")
           print(f"  Function calls: {bc.function_calls}")
           print(f"  Storage operations: {bc.storage_operations}")

           # Show function calls
           calls = bc.filter_by_type("function_call")
           if calls:
               print(f"  First few function calls:")
               for call in calls[:3]:
                   print(f"    - {call.get('name', 'Unknown')}")

Example 4: Batch Job Analysis
------------------------------

Analyze multiple recent jobs:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.models import JobStatus

   api = ProverOutputAPI()

   # Get recent jobs (last 7 days, org-wide by default; pass all_users=False for self only)
   jobs = api.list_recent_jobs(days_back=7, limit=10)

   summary = []
   for job in jobs:
       print(f"Processing job {job.job_id}...")

       if job.is_completed and job.status == JobStatus.SUCCEEDED:
           violations = api.get_violated_rules(job.job_id)
           all_checks = api.get_all_checks(job.job_id)

           summary.append({
               'job_id': job.job_id,
               'status': job.status,
               'total_checks': len(all_checks),
               'violations': len(violations),
               'project': job.project,
           })

   # Print summary table
   print(f"\n{'Job ID':<15} {'Project':<20} {'Status':<15} {'Checks':<10} {'Violations':<10}")
   print("="*80)
   for s in summary:
       print(f"{s['job_id']:<15} {s['project'] or 'N/A':<20} {s['status'].value:<15} "
             f"{s['total_checks']:<10} {s['violations']:<10}")

Example 5: Call Resolution Analysis
------------------------------------

Analyze unresolved calls in a job:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()
   unresolved_calls = api.get_call_resolutions("12345678")

   print(f"Total call resolutions: {len(unresolved_calls)}")

   # Filter for warnings
   warnings = [c for c in unresolved_calls if c.is_warning]
   print(f"Warnings: {len(warnings)}")

   # Group by resolution type
   by_resolution = {}
   for call in unresolved_calls:
       res_type = call.callee_resolution
       if res_type not in by_resolution:
           by_resolution[res_type] = []
       by_resolution[res_type].append(call)

   # Print summary
   for res_type, calls in by_resolution.items():
       print(f"\n{res_type}: {len(calls)} calls")
       for call in calls[:3]:  # Show first 3
           print(f"  {call.caller_name} -> {call.callee_name}")
           print(f"    Location: {call.source_location}")
           if call.havoc_cause:
               print(f"    Havoc cause: {call.havoc_cause}")

Example 6: Export Violation Report
-----------------------------------

Export violations to a structured format:

.. code-block:: python

   import json
   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()
   violations = api.get_violated_rules("12345678")

   # Convert to exportable format
   report = {
       'job_id': '12345678',
       'total_violations': len(violations),
       'violations': []
   }

   for v in violations:
       violation_data = {
           'rule_name': v.rule_name,
           'contract': v.contract_name,
           'method': v.method_name,
           'message': v.assert_message,
           'status': v.status.value,
           'duration': v.duration,
           'assert_type': v.assert_type.value,
       }

       if v.source_location:
           violation_data['source'] = {
               'file': v.source_location.file,
               'line': v.source_location.line,
           }

       report['violations'].append(violation_data)

   # Export to JSON
   with open('violations_report.json', 'w') as f:
       json.dump(report, f, indent=2)

   print(f"Report saved to violations_report.json")

Example 7: Custom Verification Analyzer
----------------------------------------

Build a custom analyzer class:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import ProverAPIError
   from prover_output_utility.models import JobStatus

   class VerificationAnalyzer:
       def __init__(self):
           self.api = ProverOutputAPI()

       def analyze_job(self, job_id):
           """Analyze a verification job and return summary."""
           try:
               # Get job info
               info = self.api.get_job_info(job_id)

               if info.status != JobStatus.SUCCEEDED:
                   return {
                       'status': 'incomplete',
                       'job_status': info.status.value,
                       'message': f'Job not completed: {info.status.value}'
                   }

               # Get all checks
               all_checks = self.api.get_all_checks(job_id)
               violations = [c for c in all_checks if c.is_violated]
               verified = [c for c in all_checks if c.is_verified]

               # Analyze violations
               critical_violations = []
               for v in violations:
                   if v.assert_type.value != 'SANITY_ASSERTION':
                       critical_violations.append(v)

               return {
                   'status': 'success',
                   'job_id': job_id,
                   'total_checks': len(all_checks),
                   'verified': len(verified),
                   'violations': len(violations),
                   'critical_violations': len(critical_violations),
                   'pass_rate': f"{len(verified)/len(all_checks)*100:.1f}%",
                   'details': {
                       'violations': [v.to_dict() for v in critical_violations]
                   }
               }

           except ProverAPIError as e:
               return {
                   'status': 'error',
                   'error': str(e)
               }

       def compare_jobs(self, job_id1, job_id2):
           """Compare two verification jobs."""
           result1 = self.analyze_job(job_id1)
           result2 = self.analyze_job(job_id2)

           if result1['status'] != 'success' or result2['status'] != 'success':
               return {'error': 'One or both jobs could not be analyzed'}

           return {
               'job1': job_id1,
               'job2': job_id2,
               'improvement': {
                   'violations_delta': result1['violations'] - result2['violations'],
                   'pass_rate_delta': float(result2['pass_rate'].rstrip('%')) -
                                      float(result1['pass_rate'].rstrip('%'))
               }
           }

   # Usage
   analyzer = VerificationAnalyzer()
   report = analyzer.analyze_job("12345678")
   print(report)

Example 8: Download and Cache Job Outputs
------------------------------------------

Bulk download job outputs for offline analysis:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()

   # Download all job outputs
   stats = api.download_job_outputs("12345678")

   print(f"Download Statistics:")
   print(f"  Files extracted: {stats['files_extracted']}")
   print(f"  Download size: {stats['download_size_mb']:.2f} MB")
   print(f"  Download time: {stats['download_time_s']:.2f}s")
   print(f"  Extraction time: {stats['extraction_time_s']:.2f}s")
   print(f"  Cache hit: {stats['cache_hit']}")
   print(f"  Cache directory: {stats['cache_dir']}")

   # Now you can work with local files
   api_local = ProverOutputAPI(use_local=True)
   violations = api_local.get_violated_rules(stats['cache_dir'])

Example 9: Real-time Job Monitoring with Alerts
------------------------------------------------

Monitor a job and send alerts when violations are found:

.. code-block:: python

   import time
   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.models import JobStatus

   def send_alert(message):
       """Placeholder for alert function."""
       print(f"ALERT: {message}")

   api = ProverOutputAPI()
   job_id = "12345678"

   print(f"Starting monitoring for job {job_id}")

   while True:
       status = api.get_job_status(job_id)

       if status == JobStatus.SUCCEEDED:
           violations = api.get_violated_rules(job_id)

           if violations:
               critical = [v for v in violations
                          if v.assert_type.value != 'SANITY_ASSERTION']

               if critical:
                   send_alert(f"Job {job_id} completed with {len(critical)} critical violations!")

                   for v in critical[:5]:  # Show first 5
                       send_alert(f"  - {v.rule_name}: {v.assert_message}")
               else:
                   print(f"Job completed with only sanity violations")
           else:
               print(f"Job completed successfully with no violations!")

           break

       elif status in [JobStatus.FAILED, JobStatus.CANCELED]:
           send_alert(f"Job {job_id} failed with status: {status.value}")
           break

       elif status == JobStatus.RUNNING:
           print(f"Job still running... (checking again in 30s)")
           time.sleep(30)

       else:
           time.sleep(10)
