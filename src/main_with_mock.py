#!/usr/bin/env python3
"""Mock 환경을 사용한 메인 애플리케이션"""
import os
import sys
import argparse
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config
from src.mock.mock_config import setup_mock_environment, print_mock_environment_status


class MockLegalDataPipeline:
    """Mock 환경을 사용한 법률 데이터 파이프라인"""
    
    def __init__(self, environment_type: str = "development"):
        """
        파이프라인 초기화
        
        Args:
            environment_type: Mock 환경 타입
        """
        self.environment_type = environment_type
        self.mock_env = None
        self.api_client = None
        self.db_connection = None
        
        # Mock 환경 설정
        self._setup_environment()
    
    def _setup_environment(self):
        """환경 설정"""
        print(f"🔧 {self.environment_type} 환경으로 파이프라인을 설정합니다...")
        
        if config.is_mock_enabled():
            self.mock_env = setup_mock_environment(self.environment_type)
            self.api_client = self.mock_env.get_api_client()
            self.db_connection = self.mock_env.get_db_connection()
            print("✅ Mock 환경이 설정되었습니다.")
        else:
            print("⚠️ 실제 환경이 설정되었습니다. (Mock 비활성화)")
            # 실제 클라이언트들을 여기에 설정
    
    async def fetch_law_data(self, query_params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """법령 데이터 조회"""
        if query_params is None:
            query_params = {'display': 10}
        
        print(f"📡 법령 데이터를 조회합니다... (파라미터: {query_params})")
        
        try:
            if hasattr(self.api_client, 'get_law_list_async'):
                response = await self.api_client.get_law_list_async(query_params)
            else:
                response = self.api_client.get_law_list(query_params)
            
            if 'LawSearch' in response and response['LawSearch']['law']:
                laws = response['LawSearch']['law']
                print(f"✅ {len(laws)}개의 법령을 조회했습니다.")
                return laws
            else:
                print("⚠️ 조회된 법령이 없습니다.")
                return []
                
        except Exception as e:
            print(f"❌ 법령 데이터 조회 실패: {e}")
            return []
    
    async def process_and_store_data(self, laws: List[Dict[str, Any]]) -> int:
        """데이터 처리 및 저장"""
        if not laws:
            return 0
        
        print(f"💾 {len(laws)}개의 법령 데이터를 처리하고 저장합니다...")
        
        processed_count = 0
        
        for law in laws:
            try:
                # 법령 상세 정보 조회
                law_id = law['법령ID']
                
                if hasattr(self.api_client, 'get_law_content_async'):
                    content_response = await self.api_client.get_law_content_async(law_id)
                else:
                    content_response = self.api_client.get_law_content(law_id)
                
                if 'LawContent' in content_response:
                    law_content = content_response['LawContent']['law']
                    
                    # 데이터베이스에 저장 형식으로 변환
                    document = {
                        'id': law_id,
                        'title': law_content['법령명'],
                        'content': law_content.get('법령내용', ''),
                        'doc_type': law.get('법령구분', '법률'),
                        'category': '일반',  # 기본 카테고리
                        'source': law.get('소관부처', ''),
                        'published_date': self._convert_date(law.get('공포일자', '')),
                        'status': 'active',
                        'tags': self._extract_tags(law_content.get('법령내용', '')),
                        'metadata': {
                            'bill_number': law_id,
                            'effective_date': law.get('시행일자', ''),
                            'language': 'ko'
                        }
                    }
                    
                    # 데이터베이스에 저장
                    if self.db_connection:
                        doc_id = self.db_connection.insert_document(document)
                        if doc_id:
                            processed_count += 1
                            print(f"  ✅ {law_id}: {document['title'][:50]}... 저장 완료")
                        else:
                            print(f"  ❌ {law_id}: 저장 실패")
                    
            except Exception as e:
                print(f"  ❌ {law_id}: 처리 중 오류 - {e}")
                continue
        
        print(f"📊 총 {processed_count}/{len(laws)}개 법령이 성공적으로 처리되었습니다.")
        return processed_count
    
    def _convert_date(self, date_str: str) -> str:
        """날짜 문자열을 ISO 형식으로 변환"""
        if not date_str:
            return ""
        
        # YYYYMMDD -> YYYY-MM-DDTHH:MM:SSZ 형식으로 변환
        if len(date_str) == 8 and date_str.isdigit():
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}T00:00:00Z"
        
        return date_str
    
    def _extract_tags(self, content: str) -> List[str]:
        """문서 내용에서 태그 추출"""
        keywords = [
            "개인정보", "데이터보호", "프라이버시", "정보보안", "사이버보안",
            "디지털", "인공지능", "AI", "알고리즘", "클라우드",
            "가상자산", "블록체인", "핀테크", "전자상거래",
            "공정거래", "독점금지", "소비자보호"
        ]
        
        found_tags = []
        content_lower = content.lower()
        
        for keyword in keywords:
            if keyword.lower() in content_lower:
                found_tags.append(keyword)
        
        return found_tags[:5]  # 최대 5개까지
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """데이터베이스 통계 조회"""
        if self.db_connection:
            return self.db_connection.get_statistics()
        return {}
    
    def search_documents(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """문서 검색"""
        if self.db_connection:
            return self.db_connection.search_documents(query, limit=limit)
        return []
    
    async def run_full_sync(self) -> Dict[str, Any]:
        """전체 동기화 실행"""
        print("🚀 전체 동기화를 시작합니다...")
        
        result = {
            'total_fetched': 0,
            'total_processed': 0,
            'success': False,
            'error': None
        }
        
        try:
            # 1. 법령 데이터 조회
            laws = await self.fetch_law_data({'display': 20})
            result['total_fetched'] = len(laws)
            
            # 2. 데이터 처리 및 저장
            processed_count = await self.process_and_store_data(laws)
            result['total_processed'] = processed_count
            
            # 3. 동기화 상태 업데이트
            if self.db_connection:
                sync_details = {
                    'total_fetched': result['total_fetched'],
                    'total_processed': result['total_processed'],
                    'environment_type': self.environment_type
                }
                self.db_connection.update_sync_status('api', 'completed', sync_details)
            
            result['success'] = True
            print("✅ 전체 동기화가 완료되었습니다.")
            
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ 전체 동기화 실패: {e}")
            
            if self.db_connection:
                self.db_connection.update_sync_status('api', 'failed', {'error': str(e)})
        
        return result
    
    async def run_incremental_sync(self, days: int = 7) -> Dict[str, Any]:
        """증분 동기화 실행"""
        print(f"🔄 최근 {days}일간의 증분 동기화를 시작합니다...")
        
        # 이 예제에서는 단순화하여 일반 동기화와 동일하게 처리
        return await self.run_full_sync()
    
    def cleanup(self):
        """리소스 정리"""
        if self.db_connection and hasattr(self.db_connection, 'close'):
            self.db_connection.close()
        
        if self.mock_env:
            self.mock_env.cleanup()


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Mock 환경 법률 데이터 파이프라인")
    parser.add_argument(
        "--environment", "-e",
        choices=["development", "testing", "demo"],
        default="development",
        help="환경 타입"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["full", "incremental", "search", "stats"],
        default="full",
        help="실행 모드"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="검색 쿼리 (search 모드에서 사용)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="증분 동기화 기간 (일)"
    )
    
    args = parser.parse_args()
    
    try:
        # 파이프라인 생성
        pipeline = MockLegalDataPipeline(args.environment)
        
        # Mock 환경 상태 출력
        print_mock_environment_status()
        print()
        
        if args.mode == "full":
            # 전체 동기화
            result = await pipeline.run_full_sync()
            print(f"\n📊 동기화 결과:")
            print(f"   - 조회된 법령: {result['total_fetched']}개")
            print(f"   - 처리된 법령: {result['total_processed']}개")
            print(f"   - 성공 여부: {'✅ 성공' if result['success'] else '❌ 실패'}")
            
            if result['error']:
                print(f"   - 오류: {result['error']}")
        
        elif args.mode == "incremental":
            # 증분 동기화
            result = await pipeline.run_incremental_sync(args.days)
            print(f"\n📊 증분 동기화 결과 ({args.days}일):")
            print(f"   - 조회된 법령: {result['total_fetched']}개")
            print(f"   - 처리된 법령: {result['total_processed']}개")
        
        elif args.mode == "search":
            # 문서 검색
            if not args.query:
                print("❌ 검색 모드에서는 --query 옵션이 필요합니다.")
                sys.exit(1)
            
            print(f"🔍 '{args.query}' 검색 중...")
            results = pipeline.search_documents(args.query, limit=10)
            
            print(f"\n📋 검색 결과: {len(results)}개")
            for i, doc in enumerate(results, 1):
                print(f"   {i}. {doc['title'][:60]}...")
                print(f"      ID: {doc['id']} | 타입: {doc['doc_type']} | 카테고리: {doc['category']}")
                if doc.get('tags'):
                    print(f"      태그: {', '.join(doc['tags'])}")
                print()
        
        elif args.mode == "stats":
            # 통계 조회
            stats = pipeline.get_database_statistics()
            print(f"\n📊 데이터베이스 통계:")
            print(f"   - 총 문서 수: {stats.get('total_documents', 0)}")
            print(f"   - 문서 타입별:")
            for doc_type, count in stats.get('by_doc_type', {}).items():
                print(f"     • {doc_type}: {count}개")
            print(f"   - 카테고리별:")
            for category, count in stats.get('by_category', {}).items():
                print(f"     • {category}: {count}개")
        
        # 리소스 정리
        pipeline.cleanup()
        print("\n🏁 파이프라인 실행이 완료되었습니다.")
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 파이프라인 실행 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
