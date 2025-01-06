"""Tool for fetching user details for form filling and job applications."""

from typing import Dict, Any

class UserDetailsFetcher:
    def __init__(self):
        # Mock user details for demonstration
        self._mock_user_details = {
            "personal": {
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "email": "john.doe@example.com",
                "phone": "+1-555-123-4567",
                "address": {
                    "street": "123 Main Street",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip": "94105",
                    "country": "United States"
                }
            },
            "professional": {
                "title": "Software Engineer",
                "years_experience": 5,
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
                    "graduation_year": 2018
                },
                "linkedin": "https://linkedin.com/in/johndoe",
                "github": "https://github.com/johndoe",
                "portfolio": "https://johndoe.dev"
            },
            "job_preferences": {
                "desired_role": "Senior Software Engineer",
                "desired_salary": "$120,000 - $150,000",
                "work_type": ["Remote", "Hybrid"],
                "willing_to_relocate": True,
                "preferred_locations": [
                    "San Francisco Bay Area",
                    "Seattle",
                    "New York"
                ]
            },
            "resume": {
                "summary": "Experienced software engineer with 5+ years in full-stack development...",
                "recent_experience": [
                    {
                        "company": "Tech Corp",
                        "role": "Senior Software Engineer",
                        "duration": "2020-Present",
                        "highlights": [
                            "Led team of 5 engineers in developing cloud-native applications",
                            "Reduced system latency by 40% through optimization"
                        ]
                    },
                    {
                        "company": "Startup Inc",
                        "role": "Software Engineer",
                        "duration": "2018-2020",
                        "highlights": [
                            "Developed and maintained customer-facing applications",
                            "Implemented CI/CD pipeline reducing deployment time by 60%"
                        ]
                    }
                ]
            }
        }

    def fetch_details(self) -> Dict[str, Any]:
        """
        Fetch all user details.
        
        Returns:
            Dict[str, Any]: Complete user details JSON
        """
        return {
            "success": True,
            "data": self._mock_user_details
        } 