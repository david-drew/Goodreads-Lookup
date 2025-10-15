#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from pathlib import Path
import sys, time
import re, csv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

class GoodreadsScraper:
	def __init__(self, use_selenium=True):
		self.base_url = "https://www.goodreads.com"
		self.headers = {
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
		}
		self.use_selenium = use_selenium
		self.driver = None
		
		if use_selenium:
			self._init_selenium()
	
	def _init_selenium(self):
		"""Initialize Selenium WebDriver"""
		chrome_options = Options()
		chrome_options.add_argument('--headless')
		chrome_options.add_argument('--no-sandbox')
		chrome_options.add_argument('--disable-dev-shm-usage')
		chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
		
		try:
			self.driver = webdriver.Chrome(options=chrome_options)
		except Exception as e:
			print(f"Failed to initialize Selenium: {e}")
			print("Falling back to requests-only mode (ratings may not work)")
			self.use_selenium = False
	
	def __del__(self):
		"""Close Selenium driver on cleanup"""
		if self.driver:
			self.driver.quit()
	
	def search_goodreads(self, query):
		"""Search Goodreads and return the first result URL"""
		search_url = f"{self.base_url}/search?q={query.replace(' ', '+')}"
		
		try:
			response = requests.get(search_url, headers=self.headers, timeout=10)
			response.raise_for_status()
			soup = BeautifulSoup(response.content, 'html.parser')
			
			# Find the first search result
			first_result = soup.find('a', class_='bookTitle')
			if first_result:
				href = first_result.get('href', '')
				if href.startswith('http'):
					return href
				elif href.startswith('/'):
					return self.base_url + href
				else:
					return self.base_url + '/' + href
			return None
		except Exception as e:
			print(f"Error searching: {e}")
			return None
	
	def get_book_info(self, book_url):
		"""Extract rating and review count from a book page"""
		if self.use_selenium and self.driver:
			return self._get_book_info_selenium(book_url)
		else:
			return self._get_book_info_requests(book_url)

	def _get_book_info_selenium(self, book_url):
		"""Extract rating, author, and description using Selenium (handles JavaScript)"""
		try:
			self.driver.get(book_url)
			time.sleep(3)  # Wait for JavaScript to load
			
			rating = "N/A"
			num_ratings = "N/A"
			author = "N/A"
			description = "N/A"
			
			# Try to find rating
			try:
				# Wait for rating element to be present
				rating_elem = WebDriverWait(self.driver, 10).until(
					EC.presence_of_element_located((By.CLASS_NAME, "RatingStatistics__rating"))
				)
				rating = rating_elem.text.strip()
			except:
				# Try alternative selectors
				try:
					rating_elem = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='ratingsCount']")
					rating_text = rating_elem.text
					rating_match = re.search(r'(\d+\.\d+)', rating_text)
					if rating_match:
						rating = rating_match.group(1)
				except:
					pass
			
			# Try to find number of ratings
			try:
				page_source = self.driver.page_source
				
				# Look for patterns like "1,234 ratings"
				ratings_match = re.search(r'([\d,]+)\s+ratings?', page_source)
				if ratings_match:
					num_ratings = ratings_match.group(1)
				else:
					# Try alternative pattern
					ratings_match = re.search(r'ratingCount["\']?\s*:\s*["\']?([\d,]+)', page_source)
					if ratings_match:
						num_ratings = ratings_match.group(1)
			except:
				pass
			
			# Try to find author
			try:
				# Try primary author selector
				author_elem = self.driver.find_element(By.CLASS_NAME, "ContributorLink__name")
				author = author_elem.text.strip()
			except:
				try:
					# Try alternative selector
					author_elem = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='name']")
					author = author_elem.text.strip()
				except:
					try:
						# Try finding in page source
						author_match = re.search(r'"name"\s*:\s*"([^"]+)"', page_source)
						if author_match:
							author = author_match.group(1)
					except:
						pass
			
			# Try to find description
			try:
				# Try primary description selector
				desc_elem = self.driver.find_element(By.CLASS_NAME, "DetailsLayoutRightParagraph__widthConstrained")
				description = desc_elem.text.strip()
			except:
				try:
					# Try alternative selector
					desc_elem = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='description']")
					description = desc_elem.text.strip()
				except:
					try:
						# Try finding the expandable description
						desc_elem = self.driver.find_element(By.CLASS_NAME, "BookPageMetadataSection__description")
						description = desc_elem.text.strip()
					except:
						try:
							# Look in page source for description
							desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', page_source)
							if desc_match:
								description = desc_match.group(1)
								# Unescape HTML entities
								description = description.encode().decode('unicode_escape')
						except:
							pass
			
			return {
				'rating': rating,
				'num_ratings': num_ratings,
				'author': author,
				'description': description,
				'url': book_url
			}

		except Exception as e:
			print(f"Error fetching book info with Selenium: {e}")
			return None
	
	def _get_book_info_requests(self, book_url):
		"""Extract rating using requests (fallback method)"""
		"""This was the original method, but it doesn't work with goodreads"""
		try:
			response = requests.get(book_url, headers=self.headers, timeout=10)
			response.raise_for_status()
			soup = BeautifulSoup(response.content, 'html.parser')
			
			rating = "N/A"
			num_ratings = "N/A"
			
			# Try meta tags first
			rating_meta = soup.find('meta', {'itemprop': 'ratingValue'})
			if rating_meta and rating_meta.get('content'):
				rating = rating_meta['content']
			
			ratings_meta = soup.find('meta', {'itemprop': 'ratingCount'})
			if ratings_meta and ratings_meta.get('content'):
				num_ratings = ratings_meta['content']
			
			# Try text search as fallback
			if rating == "N/A" or num_ratings == "N/A":
				page_text = soup.get_text()
				
				if rating == "N/A":
					rating_match = re.search(r'(\d+\.\d+)\s+(?:average rating|rating)', page_text)
					if rating_match:
						rating = rating_match.group(1)
				
				if num_ratings == "N/A":
					ratings_match = re.search(r'([\d,]+)\s+ratings?', page_text)
					if ratings_match:
						num_ratings = ratings_match.group(1)
			
			return {
				'rating': rating,
				'num_ratings': num_ratings,
				'url': book_url
			}
		except Exception as e:
			print(f"Error fetching book info: {e}")
			return None
	
	def get_author_books(self, author_name):
		"""Get list of English language books by an author"""
		search_url = f"{self.base_url}/search?q={author_name.replace(' ', '+')}"
		
		try:
			response = requests.get(search_url, headers=self.headers, timeout=10)
			response.raise_for_status()
			soup = BeautifulSoup(response.content, 'html.parser')
			
			# Find author link
			author_link = soup.find('a', class_='authorName')
			if not author_link:
				print(f"Author '{author_name}' not found")
				return []
			
			href = author_link.get('href', '')
			if href.startswith('http'):
				author_url = href
			elif href.startswith('/'):
				author_url = self.base_url + href
			else:
				author_url = self.base_url + '/' + href
			
			# Get author page
			response = requests.get(author_url, headers=self.headers, timeout=10)
			response.raise_for_status()
			soup = BeautifulSoup(response.content, 'html.parser')
			
			books = []
			book_links = soup.find_all('a', class_='bookTitle')
			
			for link in book_links[:20]:
				title = link.text.strip()
				href = link.get('href', '')
				
				if href.startswith('http'):
					book_url = href
				elif href.startswith('/'):
					book_url = self.base_url + href
				else:
					book_url = self.base_url + '/' + href
				
				if self.is_likely_english(title):
					books.append({
						'title': title,
						'url': book_url
					})
			
			return books
		except Exception as e:
			print(f"Error fetching author books: {e}")
			return []
	
	def is_likely_english(self, title):
		"""Basic check if title contains primarily English characters"""
		return bool(re.match(r'^[\x00-\x7F\s]+$', title))
	
	def process_input(self, query, input_type='book'):
		"""
		Process input based on type (book title or author)
		input_type: 'book', 'author', or 'auto' (attempts to detect)
		Returns a dictionary with the results
		"""
		if input_type == 'auto':
			input_type = 'book' if ' by ' in query.lower() else 'author'
		
		result = {
			'query'  : query,
			'type'   : input_type,
			'success': False,
			'data'   : None
		}
		
		if input_type == 'book':
			url = self.search_goodreads(query)
			if url:
				info = self.get_book_info(url)
				if info:
					result['success'] = True
					result['data'] = {
						'title'	  : query,
						'author'	 : info['author'],
						'description': info['description'],
						'rawrating'  : info['rating'],
						'byrating'   : get_bayesian_average(info),
						'num_ratings': info['num_ratings'],
						'url'		: info['url']
					}
		else:
			books = self.get_author_books(query)
			if books:
				result['success'] = True
				result['data'] = {
					'author'	  : query,
					'books'	   : books,
					'total_books' : len(books)
				}
		
		return result

def read_csv_to_dict(csv_path, mode='title'):
	"""
	Read a CSV file and create a dictionary based on the specified mode.
	
	Args:
		csv_path: Path to the CSV file
		mode: 'title' (default) or 'author'
			- 'title': key=title, values={'author': ..., 'description': ...}
			- 'author': key=author, values={'title': ..., 'description': ...}
	
	Returns:
		Dict organized by the specified mode
	"""
	result_dict = {}
	print(f"CSV: {csv_path}")
	
	try:
		with open(csv_path, 'r', encoding='utf-8') as f:
			reader = csv.reader(f)
			
			# Skip header row if present
			header = next(reader, None)
			
			for row in reader:
				# Skip empty rows
				if not row or not any(row):
					continue
				
				# Extract columns (pad with empty strings if needed)
				title = row[0].strip() if len(row) > 0 else ''
				author = row[1].strip() if len(row) > 1 else ''
				description = row[2].strip() if len(row) > 2 else ''
				
				if mode == 'title':
					# Key by title
					if title:
						result_dict[title] = {
							'author': author,
							'description': description
						}
				
				elif mode == 'author':
					# Key by author
					if author:
						# If author already exists, handle multiple books
						if author in result_dict:
							# Convert to list of books if not already
							if not isinstance(result_dict[author], list):
								result_dict[author] = [result_dict[author]]
							# Add new book
							result_dict[author].append({
								'title': title,
								'description': description
							})
						else:
							result_dict[author] = {
								'title': title,
								'description': description
							}
				
				else:
					raise ValueError(f"Invalid mode: '{mode}'. Use 'title' or 'author'.")
	
	except FileNotFoundError:
		print(f"Error: File '{csv_path}' not found.")
		return None
	except Exception as e:
		print(f"Error reading CSV: {e}")
		return None
	
	return result_dict

def save_results_to_file(results, filename='goodreads_results.txt'):
	"""Save results to a formatted text file"""
	with open(filename, 'w', encoding='utf-8') as f:
		f.write("=" * 80 + "\n")
		f.write("GOODREADS SEARCH RESULTS\n")
		f.write("=" * 80 + "\n\n")
		
		for i, result in enumerate(results, 1):
			f.write(f"Query #{i}: {result['query']}\n")
			f.write(f"Type: {result['type'].upper()}\n")
			f.write("-" * 80 + "\n")
			
			if not result['success']:
				f.write("Status: NO RESULTS FOUND\n\n")
				continue
			
			if result['type'] == 'book':
				data = result['data']
				f.write(f"Title: {data['title']}\n")
				f.write(f"Author: {data['author']}\n")
				f.write(f"Desc: {data['description']}\n")
				f.write(f"Rating: {data['rating']}\n")
				f.write(f"Number of Ratings: {data['num_ratings']}\n")
				f.write(f"URL: {data['url']}\n")
			
			elif result['type'] == 'author':
				data = result['data']
				f.write(f"Author: {data['author']}\n")
				f.write(f"Total English Books Found: {data['total_books']}\n\n")
				f.write("Books:\n")
				for j, book in enumerate(data['books'], 1):
					f.write(f"  {j}. {book['title']}\n")
					f.write(f"	 URL: {book['url']}\n")
			
			f.write("\n" + "=" * 80 + "\n\n")
	
	print(f"\nResults saved to: {filename}")

def simple_printer(results, filename='goodreads_results.txt'):
	with open(filename, 'w', encoding='utf-8') as f:
		for i, result in enumerate(results, 1):	
			if not result['success']:
				#f.write("Status: NO RESULTS FOUND\n\n")
				continue
			
			if result['type'] == 'book':
				data = result['data']
				f.write("-" * 80 + "\n")
				f.write(f"{data['title']}")
				f.write(f"\t{data['author']}")
				f.write(f"\t{data['byrating']}")
				f.write(f"\t{data['rawrating']} ")
				f.write(f"({data['num_ratings']})\n")
				f.write(f"{data['description']}")

def print_csv(results, filename='goodreads_results.csv'):
	with open(filename, 'w', encoding='utf-8', newline='') as f:
		writer = csv.writer(f)
		
		# Write header row
		writer.writerow(['title', 'author', 'byrating', 'rawrating', 'num_ratings', 'description'])
		
		for i, result in enumerate(results, 1):
			if not result['success']:
				continue
			
			if result['type'] == 'book':
				data = result['data']
				
				# Strip tabs and newlines from description
				description = data['description'].replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
				# Optional: collapse multiple spaces into single space
				description = re.sub(r'\s+', ' ', description).strip()
				
				# Write data row
				writer.writerow([
					data['title'],
					data['author'],
					data['byrating'],
					data['rawrating'],
					data['num_ratings'],
					description
				])

def get_search_list(list_type="csv") -> list:
	booklist = []

	if list_type != "csv":
		# Use book (epub, etc.) files in a directory to create list
		dir_path = Path("D:\\\\Books\\")

		for file_path in dir_path.iterdir():
			if file_path.is_file():
				with open(file_path, 'r') as f:
					#print(f"Found file: {file_path.name}---")
					booklist.append(file_path.name)
	else:
		# Use a specified csv_file
		#csv_file  = "Best Horror.csv"
		csv_file  = "booklist.csv"
		mode	  = "title"
		book_dict = read_csv_to_dict(csv_file, mode)

		#strip dict to list
		booklist = list(book_dict.keys())

	return booklist

def get_titles(booklist:list) -> list:
	titles = []
	for b in booklist:
		res = re.split(r'-\s*', b)
		#print(res)
		title = res.pop()
		title = title.split('.')[0]
		title_set = (title, "book")
		titles.append(title_set)
		#print(title)

	return titles

#def get_bayesian_average(rating, num_ratings, global_avg=3.5, min_ratings=10000):
def get_bayesian_average(info, global_avg=3.5, min_ratings=10000):
	rating = info['rating']
	num_ratings = info['num_ratings']

	# Convert string ratings to float if needed
	if isinstance(num_ratings, str):
		num_ratings = int(num_ratings.replace(',', ''))
		
	rating = float(rating)
	num_ratings = int(num_ratings)
		
	# Bayesian average formula
	bayesian_avg = (min_ratings * global_avg + num_ratings * rating) / (min_ratings + num_ratings)
		
	return round(bayesian_avg, 2)


def compare_ratings(rating, num_ratings, global_avg=3.5, min_ratings=10000):
	"""
	Helper function to compare raw rating vs Bayesian average.
	Useful for understanding the effect of the adjustment.
	"""
	if isinstance(num_ratings, str):
		num_ratings = int(num_ratings.replace(',', ''))
		
	rating = float(rating)
	num_ratings = int(num_ratings)
		
	bayesian = bayesian_average(rating, num_ratings, global_avg, min_ratings)
	difference = rating - bayesian
		
	print(f"\tRaw Rating: {rating}")
	print(f"\tNumber of Ratings: {num_ratings:,}")
	print(f"\tBayesian Average: {bayesian}")
	print(f"\tDifference: {difference:+.2f}")
	print(f"\tEffect: {'Pulled down' if difference > 0 else 'Pulled up'} toward global average ({global_avg})")
		
	return bayesian

def main():
	list_type = "csv"
	show_process = False

	# Initialize with Selenium (set to False to use requests only)
	scraper  = GoodreadsScraper(use_selenium=True)
	booklist = get_search_list()
	titles   = []
	results  = []

	if list_type == "csv":
		# Simple title for book list csv
		titles   = get_titles(booklist)
	elif list_type == "files":
		# For list from files
		titles = booklist

	for query, query_type in titles:
		if show_process:
			print(f"\nProcessing: {query} (type: {query_type})")
		result = scraper.process_input(query, query_type)
		results.append(result)
		
		# Print status
		if show_process:
			if result['success']:
				print(f"✓ Success")
			else:
				print(f"✗ No results found")
		
		time.sleep(2)
	
	# Save all results to file
	## save_results_to_file(results)
	#simple_printer(results)
	print_csv(results)
	
	print("\n" + "=" * 80)
	print("All queries completed!")


if __name__ == "__main__":
	main()