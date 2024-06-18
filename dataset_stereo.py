import torch
import torch.nn.functional as F
import numpy as np
import cv2
from imread_from_url import imread_from_url
import os
import sys
sys.path.append("CREStereo-Pytorch")

from nets import Model

device = 'cuda'

#Ref: https://github.com/megvii-research/CREStereo/blob/master/test.py
def inference(left, right, model, n_iter=20):

	print("Model Forwarding...")
	imgL = left.transpose(2, 0, 1)
	imgR = right.transpose(2, 0, 1)
	imgL = np.ascontiguousarray(imgL[None, :, :, :])
	imgR = np.ascontiguousarray(imgR[None, :, :, :])

	imgL = torch.tensor(imgL.astype("float32")).to(device)
	imgR = torch.tensor(imgR.astype("float32")).to(device)

	imgL_dw2 = F.interpolate(
		imgL,
		size=(imgL.shape[2] // 2, imgL.shape[3] // 2),
		mode="bilinear",
		align_corners=True,
	)
	imgR_dw2 = F.interpolate(
		imgR,
		size=(imgL.shape[2] // 2, imgL.shape[3] // 2),
		mode="bilinear",
		align_corners=True,
	)
	# print(imgR_dw2.shape)
	with torch.inference_mode():
		pred_flow_dw2 = model(imgL_dw2, imgR_dw2, iters=n_iter, flow_init=None)

		pred_flow = model(imgL, imgR, iters=n_iter, flow_init=pred_flow_dw2)
	pred_disp = torch.squeeze(pred_flow[:, 0, :, :]).cpu().detach().numpy()

	return pred_disp

if __name__ == '__main__':

    dataset_path = "/media/pablo/Nuevo_vol/Recursos Computer Vision/Recursos Computer Vision/zed-sdk/positional tracking/positional tracking/python/dataset"
    images_left = os.listdir(os.path.join(dataset_path, "left"))
    output_path_vis = os.path.join(dataset_path, "crestereo_disp_vis")
    output_path_raw = os.path.join(dataset_path, "crestereo_disp_raw")

    os.makedirs(output_path_vis, exist_ok=True)
    os.makedirs(output_path_raw, exist_ok=True)

    model_path = "CREStereo-Pytorch/models/crestereo_eth3d.pth"
	
    model = Model(max_disp=256, mixed_precision=False, test_mode=True)
    model.load_state_dict(torch.load(model_path), strict=True)
    model.to(device)
    model.eval()
	
    for image in images_left:
        left_img = cv2.imread(os.path.join(dataset_path, "left", image))
        right_img = cv2.imread(os.path.join(dataset_path, "right", image))

        in_h, in_w = left_img.shape[:2]

        # Resize image in case the GPU memory overflows
        eval_h, eval_w = (in_h,in_w)
        assert eval_h%8 == 0, "input height should be divisible by 8"
        assert eval_w%8 == 0, "input width should be divisible by 8"
        
        imgL = cv2.resize(left_img, (eval_w, eval_h), interpolation=cv2.INTER_LINEAR)
        imgR = cv2.resize(right_img, (eval_w, eval_h), interpolation=cv2.INTER_LINEAR)        

        pred = inference(imgL, imgR, model, n_iter=20)

        t = float(in_w) / float(eval_w)
        disp = cv2.resize(pred, (in_w, in_h), interpolation=cv2.INTER_LINEAR) * t

        disp_vis = (disp - disp.min()) / (disp.max() - disp.min()) * 255.0
        disp_vis = disp_vis.astype("uint8")
        disp_vis = cv2.applyColorMap(disp_vis, cv2.COLORMAP_INFERNO)

        cv2.imwrite(os.path.join(output_path_vis, image), disp_vis)

        np.save(os.path.join(output_path_raw, image.replace(".png", ".npy")), disp)

