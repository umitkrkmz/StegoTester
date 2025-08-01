# StegoTester

> A GUI-based tool for analyzing steganographic audio, image, and text content.

**StegoTester** is a desktop application for evaluating steganography outputs (audio, image, and text).  
It can compute metrics such as **MSE, PSNR, SSIM, BER, SNR, Jaccard, Levenshtein**, and text similarity scores.

With this application, you can:
- Load **Original**, **Stego**, and **Extracted** files  
- Compute multiple metrics for each supported type (audio / image / text)  
- View the results in an in‑app table  
- Export results as **TXT** or **PDF** reports

---

## Installation & Run (Single Block)

```bash
# Python 3.10+ recommended

# Clone the repository
git clone https://github.com/umitkrkmz/StegoTester.git
cd StegoTester

# Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## License

This project is released under the **MIT License**.
See [LICENSE](LICENSE) for details.

