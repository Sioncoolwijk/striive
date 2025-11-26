import requests
import json
import os
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
POSTMARK_API_KEY = os.getenv("POSTMARK_API_KEY")
POSTMARK_URL = "https://api.postmarkapp.com/email"
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL")
EMAIL_TO = os.getenv("EMAIL_TO")
STRIIVE_COOKIE = os.getenv("STRIIVE_COOKIE")
STRIIVE_INBOX_URL = os.getenv("STRIIVE_INBOX_URL", "https://freelancer.striive.com/inbox/all")
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

URL = "https://freelancer.striive.com/api/v2/job-requests?page=0&size=1000&maxRadius=50&sortBy=&sortOrder=ASCENDING&clientNames=&professionalTypes=&remoteAllowed=&locations=&skills="

FETCH_HEADERS = {
    "Cookie": STRIIVE_COOKIE or "",
    "User-Agent": "Mozilla/5.0 (compatible; JobMonitor/1.0)",
    "Accept": "application/json"
}


def send_email(job: Dict[str, Any]) -> bool:
    """
    Send email notification for a new job.
    
    Args:
        job: Job dictionary containing job details
        
    Returns:
        True if email sent successfully, False otherwise
    """
    if not POSTMARK_API_KEY:
        logger.error("POSTMARK_API_KEY is not set. Cannot send email.")
        return False

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": POSTMARK_API_KEY
    }

    url = STRIIVE_INBOX_URL

    # Collect optional fields safely
    fields = [
        ("Title", job.get("title")),
        ("State", job.get("state")),
        ("Start date", job.get("startDate")),
        ("End date", job.get("endDate")),
        ("Published", job.get("publishedAt")),
        ("Hours per week", job.get("hoursPerWeek")),
        ("Min hours per week", job.get("minHoursPerWeek")),
        ("Type of professional", job.get("typeOfProfessional")),
        ("Remote allowed", job.get("remoteAllowed")),
        ("Reference", job.get("referenceCode")),
        ("Location", job.get("locationName")),
        ("Client", job.get("client", {}).get("name") if job.get("client") else None),
        ("ID", job.get("id")),
    ]

    # Build HTML lines only for fields that exist and are not None
    field_lines = ""
    for label, value in fields:
        if value is None:
            continue
        field_lines += f"<p><strong>{label}:</strong> {value}</p>"

    subject = f"New engineer job: {job.get('title', 'Unknown')}"

    html_body = f"""
        <h2>New engineer job found</h2>
        <p>Apply here: <a href="{url}">{url}</a></p>
        {field_lines}
    """

    payload = {
        "From": POSTMARK_FROM_EMAIL,
        "To": EMAIL_TO,
        "Subject": subject,
        "HtmlBody": html_body,
        "MessageStream": "outbound"
    }

    try:
        r = requests.post(POSTMARK_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        logger.info(f"Email sent successfully for job ID: {job.get('id')}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send email for job ID {job.get('id')}: {e}")
        return False


def is_recent_job(job: Dict[str, Any]) -> bool:
    """
    Check if a job was published in the last 24 hours.
    
    Args:
        job: Job dictionary
        
    Returns:
        True if job was published in the last 24 hours, False otherwise
    """
    published_at = job.get("publishedAt")
    if not published_at:
        return False
    
    try:
        # Parse the published_at timestamp (assuming ISO format)
        published_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        if published_time.tzinfo is None:
            published_time = published_time.replace(tzinfo=timezone.utc)
        
        # Check if published within last 24 hours
        now = datetime.now(timezone.utc)
        time_diff = now - published_time
        
        return time_diff <= timedelta(hours=24)
    except (ValueError, AttributeError) as e:
        logger.warning(f"Error parsing publishedAt for job {job.get('id')}: {e}")
        return False


def fetch_jobs() -> Optional[list]:
    """
    Fetch jobs from the API with retry logic.
    
    Returns:
        List of jobs or None if fetch failed
    """
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Fetching jobs (attempt {attempt + 1}/{MAX_RETRIES})...")
            r = requests.get(URL, headers=FETCH_HEADERS, timeout=30)
            r.raise_for_status()
            
            try:
                jobs = r.json()
                if not isinstance(jobs, list):
                    logger.error(f"Unexpected response type. Expected list, got {type(jobs)}")
                    logger.debug(f"Response content: {jobs}")
                    return None
                
                logger.info(f"Successfully fetched {len(jobs)} jobs")
                return jobs
            except json.JSONDecodeError as e:
                logger.error(f"Response is not valid JSON: {e}")
                logger.debug(f"Response text: {r.text[:500]}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                    continue
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Giving up.")
                return None
    
    return None


def is_relevant_job(job: Dict[str, Any]) -> bool:
    """
    Check if a job is relevant (contains 'engineer' or 'data' in title).
    
    Args:
        job: Job dictionary
        
    Returns:
        True if job is relevant, False otherwise
    """
    title = job.get("title", "").lower()
    return "engineer" in title or "data" in title


def run() -> None:
    """
    Main function to run the job monitor.
    """
    logger.info("Starting job monitor...")
    
    # Validate configuration
    if not POSTMARK_API_KEY:
        logger.error("POSTMARK_API_KEY environment variable is not set!")
        sys.exit(1)
    
    if not POSTMARK_FROM_EMAIL:
        logger.error("POSTMARK_FROM_EMAIL environment variable is not set!")
        sys.exit(1)
    
    if not EMAIL_TO:
        logger.error("EMAIL_TO environment variable is not set!")
        sys.exit(1)
    
    if not STRIIVE_COOKIE:
        logger.error("STRIIVE_COOKIE environment variable is not set!")
        sys.exit(1)
    
    # Fetch jobs
    jobs = fetch_jobs()
    if jobs is None:
        logger.error("Failed to fetch jobs. Exiting.")
        sys.exit(1)
    
    # Process jobs
    new_jobs_count = 0
    emails_sent = 0
    
    for job in jobs:
        # Check if job is relevant
        if not is_relevant_job(job):
            continue
        
        # Check if job was published in the last 24 hours
        if not is_recent_job(job):
            continue
        
        job_id = job.get("id")
        if not job_id:
            logger.warning(f"Job missing ID: {job.get('title', 'Unknown')}")
            continue
        
        # Send email for new job
        logger.info(f"New job found: {job.get('title')} (ID: {job_id}, published: {job.get('publishedAt')})")
        if send_email(job):
            emails_sent += 1
        new_jobs_count += 1
    
    logger.info(f"Run completed. New jobs: {new_jobs_count}, Emails sent: {emails_sent}")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)