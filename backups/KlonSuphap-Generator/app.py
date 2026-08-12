import spaces
import gradio as gr
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM

model_name = "Kongfha/KlonSuphap-LM"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

nlp = pipeline("text-generation",
                    model=model,
                    tokenizer=tokenizer)

def remove_non_thai_characters(text):
    thai_characters = []
    for char in text:
        if ord(char) >= 3584 and ord(char) <= 3711 or char == '\n' or char == '\t':
            if char == '\t':
                thai_characters.append('    ')
            else:
                thai_characters.append(char)
    return ''.join(thai_characters)

@spaces.GPU
def generate(input_sentence, auto_rhyme_tag, top_p=0.8, temperature=0.8, max_length=170):
    generated_text = nlp(input_sentence,
                        max_length=int(max_length),
                        top_p=float(top_p),
                        temperature=float(temperature))
    raw_output = generated_text[0]['generated_text']
    output = remove_non_thai_characters(raw_output)
    return output

inputs = [
    gr.Textbox(label="Input Sentence"),
    gr.Checkbox(label="Auto Rhyme-Tag for Input (not done)"),
    gr.Slider(minimum=0.1, maximum=1.0, value=0.8, label="Top P", step=0.05),
    gr.Slider(minimum=0.1, maximum=2.0, value=0.8, label="Temperature", step=0.05),
    gr.Number(value=100, label="Max Length")
]

outputs = gr.Textbox(label="Generated Text")

examples = [
    ["เรือล่อง", False, 0.8, 0.8, 100],
    ["แม้นชีวี", False, 0.8, 0.8, 100],
    ["หากวันใด", False, 0.8, 0.8, 100],
    ["หากจำเป็น", False, 0.8, 0.8, 100]
]

iface = gr.Interface(
  fn=generate,
  inputs=inputs,
  outputs=outputs,
  examples=examples,
  title="🌾 KlonSuphap-Generator (แต่งกลอน 8 ด้วย GPT-2)",
  description="โมเดลนี้เป็นโมเดลที่พัฒนาต่อยอดมาจาก PhraAphaiManee-LM โดยพัฒนาให้โมเดลสามารถแต่งกลอนออกมาให้ถูกฉันทลักษณ์มากยิ่งขึ้น <br> \
                สามารถเข้าถึงโมเดลผ่าน Hugging Face ได้จาก -> [Kongfha/KlonSuphap-LM](https://huggingface.co/Kongfha/KlonSuphap-LM) <br>\
                *หมายเหตุ: ถ้าต้องการที่จะ Input ด้วยวรรคทั้งวรรค จะต้องใส่ \<s2> และ \</s2> ครอบพยางค์สุดท้ายของวรรคด้วย* <br> \
                *ตัวอย่าง: สัมผัสเส้นขอบฟ้าชลา\<s2>ลัย\</s2>*"
)

iface.launch(theme=gr.themes.Soft(primary_hue="amber", neutral_hue="sky").set(block_info_text_size="*text_md"))