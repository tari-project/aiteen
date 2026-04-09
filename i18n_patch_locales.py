def run_pipeline_if_pr():
    # Placeholder for pipeline execution on PR trigger
    return True

def check_pr_and_run_pipeline(is_pr):
    if is_pr:
        return run_pipeline_if_pr()
    return False
