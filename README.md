# Goodreads-Lookup
Scrapes goodreads for book info and ratings.  Also retrieves list of books by author.  Provides raw and bayesian weighted average ratings scores.

To Do:
- Clean up, organize, and split into multiple files.  Maybe.
- Author and Book modes return different info, which is intended but maybe not ideal.

# Bayesian Weighted Averages
A BWA rating adjusts the rating score towards the average depending on the number of ratings. Fewer ratings means the raw score is trusted less, so the score is pushed harder towards the average.

Use min_ratings to tune the weighting as follows:
min_ratings = 5,000:  Lenient, trusts books faster
min_ratings = 10,000: Balanced (current default)
min_ratings = 25,000: Conservative, only medium+ popularity books get full weight
min_ratings = 50,000: Very conservative, best for comparing extremely-popular books
