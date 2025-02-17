from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle


def authenticate_youtube():
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", scopes
            )
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

def is_official_ablum_song(tags, title):
    if not tags:
        tags = []
    
    unwatend_keywords = ['live', 'remix', 'cover', 'performance', 'concert', 'karaoke', 'instrumental']

    if not any(unwanted in title.lower() for unwanted in unwatend_keywords):
        return True
    return False

def is_licensed_content(content_details):
    return content_details.get("licensedContent", False)

def is_not_news(snippet):

    title = snippet["title"].lower()
    description = snippet.get("description", "").lower()
    category_id = snippet.get("categoryId", "")

    # 뉴스 콘텐츠를 제외하는 키워드와 카테고리 ID
    news_keywords = ["뉴스", "news", "breaking", "headline"]
    news_category_id = "25"  # News & Politics 카테고리 ID

    # 뉴스 키워드가 제목/설명에 없고, categoryId가 뉴스가 아닌 경우
    if all(keyword not in title for keyword in news_keywords) and \
       all(keyword not in description for keyword in news_keywords) and \
       category_id != news_category_id:
        return True

    return False

def is_music_category(snippet):
    return snippet.get('categoryId', '') == '10'

def clean_text(text):
    try:
        cleaned_text = ''.join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))
        return cleaned_text
    except Exception as e:
        print(f"텍스트 클린 중 오류 발생: {e}")
        return ""

def create_playlist(youtube, playlist_name, description=""):
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": playlist_name,
                "description": description,
                "tags": ["music", "auto-generated", "playlist"],
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": "private"  # private, public, unlisted
            }
        }
    )
    response = request.execute()
    return response

def add_video_to_playlist(youtube, playlist_id, video_id):
    request = youtube.playlistItems().insert(
        part='snippet',
        body={
            'snippet': {
                'playlistId': playlist_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video_id
                }
            }
        }
    )
    response = request.execute()
    return response

def search_music(youtube, query, max_results=50):
    try:
        search_request = youtube.search().list(
            part="id",
            q=query,
            type="video",
            maxResults=max_results
        )
        search_response = search_request.execute()

        video_ids = [item["id"]["videoId"] for item in search_response.get("items", []) if "videoId" in item["id"]]

        if not video_ids:
            print("검색 결과에 유효한 동영상이 없습니다.")
            return []

        video_request = youtube.videos().list(
            part="snippet, contentDetails",
            id=",".join(video_ids)
        )
        video_response = video_request.execute()

        results = []
        for item in video_response.get("items", []):
            snippet = item["snippet"]
            content_details = item["contentDetails"]
            video_id = item["id"]

            tags = snippet.get('tags', [])
            title = clean_text(snippet['title'])
            channel_title = clean_text(snippet['channelTitle'])
            url = f'https://www.youtube.com/watch?v={video_id}'

            if is_licensed_content(content_details) and is_music_category(snippet) and is_not_news(snippet) and is_official_ablum_song(tags, title):
                results.append([video_id, title, channel_title, url])
        
        return results

    except Exception as e:
        print(f"노래 검색 중 오류 발생: {e}")
        return []

# 메인 실행 로직
def main():
    # 1. OAuth 인증
    youtube = authenticate_youtube()

    # 2. 사용자로부터 플레이리스트 이름 및 검색어 입력
    playlist_name = input("생성할 라이브러리(플레이리스트) 이름을 입력하세요: ")
    description = input("플레이리스트에 대한 설명을 입력하세요 (선택, 공백 가능): ")
    search_query = input("검색어를 입력하세요 (예: '최신 걸그룹 노래'): ")
    max_results = int(input("검색 결과를 몇 개 출력할지 입력하세요 (예: 50): "))

    # 3. 플레이리스트 생성
    try:
        playlist_response = create_playlist(youtube, playlist_name, description)
        playlist_id = playlist_response['id']
        print(f"\n플레이리스트가 성공적으로 생성되었습니다!")
        print(f"플레이리스트 ID: {playlist_name}\n")
    except Exception as e:
        print(f"플레이리스트 생성 중 오류 발생: {e}")
        return

    # 4. 검색 및 Official 노래 필터링
    print("\n🔍 검색 및 필터링 중...")
    try:
        songs = search_music(youtube, search_query, max_results=max_results)
        if not songs:
            print('조건에 맞는 노래가 없습니다.')
            return

        print("\n🎵 검색된 노래를 플레이리스트에 추가중..")
        for idx, (video_id, title, channel, url) in enumerate(songs, start=1):
            add_video_to_playlist(youtube, playlist_id, video_id)
            print(f"{idx}. 제목: {title}")
            print(f"   가수명(채널명): {channel}")
            print(f"   링크: {url}\n")
        print('모든 노래가 플레이리스트에 추가되었습니다 !')
    except Exception as e:
        print(f"검색 중 오류 발생: {e}")

if __name__ == "__main__":
    main()