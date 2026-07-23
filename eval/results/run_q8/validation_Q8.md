# Q8 Validation Report

Status: PASSED
Question: Why do fuzzy commitments offer insufficient protection according to this paper?
Answer:
According to this paper, fuzzy commitments offer insufficient protection because the reconstructed images are sufficiently close to those of the user to allow unlocking their account even at very low failure rates (0.1% FAR). However, these reconstructions can still be used to infer private information about the user, such as gender, age, or ethnicity, suggesting that with high probability, the reconstruction is successful and can reveal sensitive data. Additionally, the paper discusses how fuzzy commitments do not provide irreversibility or unlinkability; a compromised system’s reconstructed image could potentially unlock accounts in other systems.
