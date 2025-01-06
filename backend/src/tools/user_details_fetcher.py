"""Tool for fetching user details for form filling."""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class UserDetailsFetcher:
    """Fetches user details for form filling."""
    
    def __init__(self):
        # Mock user details - in a real implementation, this would be fetched from a database or API
        self.mock_user_details = {
            "personal": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1 (555) 123-4567",
                "address": {
                    "street": "123 Main Street",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip": "94105",
                    "country": "United States"
                },
                "date_of_birth": "1990-01-01"
            },
            "professional": {
                "current_title": "Software Engineer",
                "years_of_experience": 5,
                "skills": [
                    "Python",
                    "JavaScript",
                    "React",
                    "Node.js",
                    "AWS"
                ],
                "education": {
                    "degree": "Bachelor of Science",
                    "major": "Computer Science",
                    "university": "Stanford University",
                    "graduation_year": 2015
                },
                "linkedin": "https://linkedin.com/in/johndoe",
                "github": "https://github.com/johndoe",
                "portfolio": "https://johndoe.dev"
            },
            "preferences": {
                "desired_role": "Senior Software Engineer",
                "desired_salary": "$150,000",
                "willing_to_relocate": True,
                "preferred_work_type": "Remote",
                "notice_period": "2 weeks"
            }
        }

    def fetch_details(self) -> Dict[str, Any]:
        """
        Fetch all user details.
        
        Returns:
            Dictionary containing all user details
        """
        logger.info("Fetching all user details")
        
        try:
            return {
                "success": True,
                "data": self.mock_user_details
            }
        except Exception as e:
            logger.error(f"Error fetching user details: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to fetch user details: {str(e)}"
            } 