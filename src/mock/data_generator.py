"""Mock 데이터 생성기"""
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import os

class MockDataGenerator:
    """개발환경용 Mock 데이터 생성기"""
    
    def __init__(self):
        self.doc_types = ["법률", "판례", "고시", "시행령", "규칙"]
        self.categories = ["정보보호", "공정거래", "민사", "행정", "금융", "과학기술", "정보통신"]
        self.sources = [
            "국회 법제사법위원회", "국회 정무위원회", "국회 과학기술정보방송통신위원회",
            "대법원", "서울행정법원", "서울중앙지방법원",
            "과학기술정보통신부", "공정거래위원회", "금융위원회"
        ]
        self.statuses = ["active", "draft", "deprecated"]
        
        # 법률 관련 키워드
        self.legal_keywords = [
            "개인정보보호", "데이터보호", "프라이버시", "정보보안", "사이버보안",
            "디지털플랫폼", "인공지능", "AI", "알고리즘", "클라우드",
            "가상자산", "블록체인", "핀테크", "디지털금융", "전자상거래",
            "공정거래", "독점금지", "불공정거래", "소비자보호", "디지털권리"
        ]
        
        # 일반적인 법조문 템플릿
        self.article_templates = [
            "제{article}조(목적) 이 법은 {subject}에 관한 사항을 규정함으로써 {purpose}에 이바지함을 목적으로 한다.",
            "제{article}조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.\n1. \"{term}\"란 {definition}을 말한다.",
            "제{article}조({title}) {content}는 다음 각 호의 사항을 준수하여야 한다.\n1. {item1}\n2. {item2}\n3. {item3}",
            "제{article}조(금지행위) 다음 각 호의 행위는 이를 금지한다.\n1. {prohibition1}\n2. {prohibition2}",
        ]
        
        # 판례 템플릿
        self.case_templates = [
            "【판시사항】\n{case_point}\n\n【판결요지】\n{case_summary}",
            "【사건개요】\n{case_background}\n\n【법원의 판단】\n{court_decision}",
            "【쟁점】\n1. {issue1}\n2. {issue2}\n\n【판단】\n{judgment}"
        ]

    def generate_legal_document(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """단일 법률 문서 생성"""
        if not doc_id:
            doc_id = f"{random.choice(['LAW', 'CASE', 'REG'])}-{datetime.now().year}-{random.randint(1, 999):03d}"
        
        doc_type = random.choice(self.doc_types)
        category = random.choice(self.categories)
        
        # 문서 제목 생성
        keyword = random.choice(self.legal_keywords)
        if doc_type == "법률":
            title = f"{keyword} {random.choice(['기본법', '특별법', '개정법'])} 제정안"
        elif doc_type == "판례":
            title = f"{keyword} 관련 {random.choice(['손해배상', '행정소송', '민사', '형사'])} 판례"
        elif doc_type == "고시":
            title = f"{keyword} {random.choice(['관리체계', '인증기준', '운영지침'])} 고시"
        elif doc_type == "시행령":
            title = f"{keyword} {random.choice(['법률', '규칙'])} 시행령"
        else:  # 규칙
            title = f"{keyword} {random.choice(['운영', '관리', '시행'])} 규칙"
        
        # 콘텐츠 생성
        content = self._generate_content(doc_type, keyword)
        
        # 발행일 생성 (최근 1년 내)
        published_date = self._generate_random_date()
        
        # 메타데이터 생성
        metadata = self._generate_metadata(doc_type, doc_id)
        
        # 태그 생성
        tags = self._generate_tags(keyword, doc_type)
        
        return {
            "id": doc_id,
            "title": title,
            "content": content,
            "doc_type": doc_type,
            "category": category,
            "source": random.choice(self.sources),
            "published_date": published_date.isoformat() + "Z",
            "status": random.choice(self.statuses),
            "tags": tags,
            "metadata": metadata
        }

    def generate_multiple_documents(self, count: int) -> List[Dict[str, Any]]:
        """여러 법률 문서 생성"""
        documents = []
        used_ids = set()
        
        for _ in range(count):
            while True:
                doc_id = f"{random.choice(['LAW', 'CASE', 'REG'])}-{datetime.now().year}-{random.randint(1, 999):03d}"
                if doc_id not in used_ids:
                    used_ids.add(doc_id)
                    break
            
            documents.append(self.generate_legal_document(doc_id))
        
        return documents

    def save_mock_data(self, documents: List[Dict[str, Any]], filename: str = "mock_legal_documents.json"):
        """Mock 데이터를 파일로 저장"""
        # sample_data 디렉토리가 없으면 생성
        sample_data_dir = Path("sample_data")
        sample_data_dir.mkdir(exist_ok=True)
        
        file_path = sample_data_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        
        return str(file_path)

    def load_mock_data(self, filename: str = "legal_documents.json") -> List[Dict[str, Any]]:
        """기존 Mock 데이터 로드"""
        sample_data_dir = Path("sample_data")
        file_path = sample_data_dir / filename
        
        if not file_path.exists():
            # 파일이 없으면 새로운 Mock 데이터 생성
            documents = self.generate_multiple_documents(10)
            self.save_mock_data(documents, filename)
            return documents
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _generate_content(self, doc_type: str, keyword: str) -> str:
        """문서 타입에 따른 콘텐츠 생성"""
        if doc_type == "판례":
            return self._generate_case_content(keyword)
        else:
            return self._generate_law_content(keyword)

    def _generate_law_content(self, keyword: str) -> str:
        """법률/규정 콘텐츠 생성"""
        articles = []
        article_num = 1
        
        # 목적 조항
        purpose_text = random.choice([
            f"{keyword}의 건전한 발전과 이용자 보호",
            f"{keyword} 관련 질서 확립과 공정성 확보", 
            f"{keyword}에 관한 국민의 권익 보호와 안전성 확보"
        ])
        
        articles.append(
            self.article_templates[0].format(
                article=article_num,
                subject=keyword,
                purpose=purpose_text
            )
        )
        article_num += 1
        
        # 정의 조항
        term = keyword.split()[0] if ' ' in keyword else keyword
        definition = f"{keyword}과 관련된 기술, 서비스, 또는 활동"
        
        articles.append(
            self.article_templates[1].format(
                article=article_num,
                term=term,
                definition=definition
            )
        )
        article_num += 1
        
        # 의무사항 조항
        obligations = [
            "투명성과 공정성 확보",
            "이용자의 권익 보호", 
            "관련 법령의 준수"
        ]
        
        articles.append(
            self.article_templates[2].format(
                article=article_num,
                title="사업자의 의무",
                content="사업자",
                item1=obligations[0],
                item2=obligations[1], 
                item3=obligations[2]
            )
        )
        
        return "\n\n".join(articles)

    def _generate_case_content(self, keyword: str) -> str:
        """판례 콘텐츠 생성"""
        template = random.choice(self.case_templates)
        
        if "판시사항" in template:
            return template.format(
                case_point=f"{keyword} 관련 사업자의 의무 위반시 손해배상 책임",
                case_summary=f"{keyword} 서비스 제공 시 이용자에게 발생한 피해에 대해 사업자가 충분한 주의의무를 다하지 않은 경우 손해배상 책임을 진다."
            )
        elif "사건개요" in template:
            return template.format(
                case_background=f"피고는 {keyword} 관련 서비스를 제공하는 업체로, 원고는 해당 서비스 이용 중 피해를 입었다고 주장하며 손해배상을 구하였다.",
                court_decision=f"법원은 {keyword} 서비스 제공자는 이용자 보호를 위한 합리적 조치를 취할 의무가 있다고 판시하였다."
            )
        else:  # 쟁점
            return template.format(
                issue1=f"{keyword} 서비스 제공자의 주의의무 범위",
                issue2="손해 발생과 서비스 제공자의 과실 간 인과관계",
                judgment=f"{keyword} 관련 사업에서도 일반적인 주의의무 기준이 적용되며, 기술의 특수성을 고려하여 합리적 수준의 보안 조치를 요구한다고 판단하였다."
            )

    def _generate_random_date(self) -> datetime:
        """최근 1년 내 랜덤 날짜 생성"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        random_days = random.randint(0, 365)
        return start_date + timedelta(days=random_days)

    def _generate_metadata(self, doc_type: str, doc_id: str) -> Dict[str, Any]:
        """문서 타입별 메타데이터 생성"""
        base_metadata = {"language": "ko"}
        
        if doc_type == "법률":
            base_metadata.update({
                "bill_number": doc_id.split('-')[-1],
                "proposer": f"{random.choice(['김', '이', '박', '최', '정'])}{random.choice(['민수', '영희', '철수', '순희', '건우'])} 의원 외 {random.randint(5, 30)}인",
                "committee": random.choice([
                    "법제사법위원회", "정무위원회", "과학기술정보방송통신위원회",
                    "산업통상자원중소벤처기업위원회"
                ])
            })
        elif doc_type == "판례":
            base_metadata.update({
                "case_number": f"{random.randint(2020, 2024)}{random.choice(['다', '가합', '구합'])}{random.randint(10000, 99999)}",
                "court": random.choice(["대법원", "서울행정법원", "서울중앙지방법원", "서울고등법원"]),
                "date_decided": self._generate_random_date().strftime("%Y-%m-%d"),
                "judge": f"{random.choice(['김', '이', '박', '최', '정'])}{random.choice(['판사', '대법관'])}"
            })
        elif doc_type in ["고시", "시행령", "규칙"]:
            base_metadata.update({
                "notice_number" if doc_type == "고시" else "decree_number": f"{random.randint(2024, 2025)}-{random.randint(1, 50):02d}",
                "department": random.choice([
                    "과학기술정보통신부", "공정거래위원회", "금융위원회", "기획재정부"
                ]),
                "effective_date": (self._generate_random_date() + timedelta(days=random.randint(30, 90))).strftime("%Y-%m-%d")
            })
        
        return base_metadata

    def _generate_tags(self, keyword: str, doc_type: str) -> List[str]:
        """키워드와 문서 타입을 기반으로 태그 생성"""
        tags = [keyword.replace(' ', '')]
        
        # 문서 타입별 추가 태그
        if doc_type == "판례":
            tags.extend(["판례", random.choice(["손해배상", "민사책임", "행정소송"])])
        elif doc_type == "법률":
            tags.extend(["법률", random.choice(["제정", "개정", "특별법"])])
        elif doc_type == "고시":
            tags.extend(["고시", random.choice(["인증", "기준", "지침"])])
        
        # 카테고리 기반 추가 태그
        additional_tags = {
            "정보보호": ["보안", "프라이버시", "개인정보"],
            "공정거래": ["경쟁", "독점", "소비자보호"],
            "금융": ["핀테크", "디지털금융", "가상자산"],
            "과학기술": ["AI", "빅데이터", "IoT"]
        }
        
        for category, category_tags in additional_tags.items():
            if category in keyword or any(tag in keyword for tag in category_tags):
                tags.extend(random.sample(category_tags, min(2, len(category_tags))))
                break
        
        # 중복 제거하고 최대 5개까지
        return list(set(tags))[:5]

    def generate_api_response_mock(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """API 응답 Mock 데이터 생성"""
        if endpoint == "lawList.do":
            return self._generate_law_list_response(params)
        elif endpoint == "lawContent.do":
            return self._generate_law_content_response(params)
        elif endpoint == "lawArticles.do":
            return self._generate_law_articles_response(params)
        else:
            return {"error": "Unknown endpoint"}

    def _generate_law_list_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """법령 목록 API 응답 생성"""
        page_size = params.get('display', 10)
        documents = self.generate_multiple_documents(page_size)
        
        # API 응답 형식에 맞게 변환
        law_list = []
        for doc in documents:
            law_list.append({
                "법령ID": doc["id"],
                "법령명": doc["title"],
                "법령구분": doc["doc_type"],
                "소관부처": doc["source"],
                "공포일자": doc["published_date"][:10].replace('-', ''),
                "시행일자": doc["published_date"][:10].replace('-', ''),
                "법령상태": "현행" if doc["status"] == "active" else "폐지"
            })
        
        return {
            "LawSearch": {
                "law": law_list,
                "totalCnt": len(law_list),
                "display": page_size,
                "start": params.get('start', 1)
            }
        }

    def _generate_law_content_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """법령 내용 API 응답 생성"""
        law_id = params.get('LSO_ID', 'LAW-2024-001')
        document = self.generate_legal_document(law_id)
        
        return {
            "LawContent": {
                "law": {
                    "법령ID": document["id"],
                    "법령명": document["title"],
                    "법령내용": document["content"],
                    "공포일자": document["published_date"][:10].replace('-', ''),
                    "시행일자": document["published_date"][:10].replace('-', '')
                }
            }
        }

    def _generate_law_articles_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """법령 조문 API 응답 생성"""
        law_id = params.get('LSO_ID', 'LAW-2024-001')
        
        # 조문들 생성
        articles = []
        for i in range(1, random.randint(5, 15)):
            articles.append({
                "조문번호": f"제{i}조",
                "조문제목": f"조항{i}",
                "조문내용": f"제{i}조의 내용입니다. " + " ".join([
                    random.choice(self.legal_keywords) + "에 관한",
                    random.choice(["규정", "사항", "기준", "원칙"]) + "을",
                    "명시한 조문입니다."
                ])
            })
        
        return {
            "LawArticles": {
                "articles": articles,
                "법령ID": law_id,
                "totalCnt": len(articles)
            }
        }


# 편의 함수들
def create_mock_data(count: int = 50) -> str:
    """지정된 개수의 Mock 데이터를 생성하고 파일로 저장"""
    generator = MockDataGenerator()
    documents = generator.generate_multiple_documents(count)
    file_path = generator.save_mock_data(documents, f"mock_legal_documents_{count}.json")
    print(f"Mock 데이터 {count}개가 {file_path}에 생성되었습니다.")
    return file_path

def load_existing_mock_data() -> List[Dict[str, Any]]:
    """기존 Mock 데이터 로드"""
    generator = MockDataGenerator()
    return generator.load_mock_data()


if __name__ == "__main__":
    # 테스트용 코드
    generator = MockDataGenerator()
    
    # 단일 문서 생성
    doc = generator.generate_legal_document()
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    
    # 여러 문서 생성 및 저장
    create_mock_data(20)
