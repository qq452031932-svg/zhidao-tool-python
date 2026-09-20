"""用原系统 prompt 生成单条百度知道回答。"""

from pathlib import Path

from lxds.deepseek import chat


STYLES = ("first_person", "third_person", "helper")
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_STYLE_FILES = {
    "first_person": "qa_style1_first_person.txt",
    "third_person": "qa_style2_third_person.txt",
    "helper": "qa_style3_helper.txt",
}


def generate_answer(api_key: str, question: str, style: str = "first_person") -> str:
    """选定风格并追加真人感后缀；不包装或改写模型回答。"""
    if style not in STYLES:
        raise ValueError(f"不支持的问答风格：{style}")
    system_prompt = (_PROMPT_DIR / _STYLE_FILES[style]).read_text(encoding="utf-8")
    human_suffix = (_PROMPT_DIR / "qa_human_suffix.txt").read_text(encoding="utf-8")
    return chat(
        api_key,
        [
            {"role": "system", "content": system_prompt + human_suffix},
            {"role": "user", "content": question},
        ],
        json_mode=False,
    )
