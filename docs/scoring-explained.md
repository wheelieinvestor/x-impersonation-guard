# Scoring explained

Each candidate receives weighted signals:

- Handle similarity: 20
- Display name similarity: 15
- Bio similarity: 10
- Profile image similarity: 25
- Account age: 10
- Follower ratio: 5
- Follow-back pattern: 5
- Posting behavior: 5
- Verified status: 5

Scores below 40 are discarded. Scores from 40 to 69 are stored as low confidence. Scores from 70 to 89 enter the review queue as medium priority. Scores from 90 to 100 enter the review queue as high priority. Near-identical profile images plus similar handles are critical.
