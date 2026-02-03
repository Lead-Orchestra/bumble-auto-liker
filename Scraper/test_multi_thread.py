import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add Scraper directory to path
sys.path.append(str(Path(__file__).parent))

from bumble_profile_scraper import scrape_worker

class TestMultiThreading(unittest.TestCase):
    @patch('bumble_profile_scraper.scrape_profiles')
    def test_worker_wrapper(self, mock_scrape):
        """Test that worker_wrapper correctly calls scrape_profiles with staggered start"""
        args_dict = {
            'limit': 1,
            'delay': 1.0,
            'headless': True,
            'stagger': 0 # No wait for test
        }
        
        # Test worker 0
        result = scrape_worker(0, 2, args_dict.copy())
        self.assertTrue(result)
        mock_scrape.assert_called_once()
        
        # Check that output file was generated automatically or modified
        call_args = mock_scrape.call_args[1]
        self.assertIn('worker0', call_args['output_file'])

    @patch('bumble_profile_scraper.scrape_profiles')
    def test_worker_with_custom_output(self, mock_scrape):
        """Test worker correctly names output files when a base name is provided"""
        args_dict = {
            'output_file': 'results.json',
            'limit': 1,
            'stagger': 0
        }
        
        scrape_worker(1, 2, args_dict)
        call_args = mock_scrape.call_args[1]
        self.assertEqual(call_args['output_file'], 'results_worker1.json')

if __name__ == '__main__':
    unittest.main()
